"""elder_npc — 火焰議會（長老會）六位長老的 NPC 回覆模組（RAG 版）。

六位長老都是「非主要角色」：只依角色設定、當前場景、對話紀錄、story.db 檢索到的故事
與「主角 × 達索親密度」以角色身分回應主角；不改動數值、不推進階段、不改寫真相度或旗標。

長老 key：
  morgan    獵燼長老・莫爾甘（「邊境肅清」征伐將軍）
  melku     審查長老・梅爾庫（「輪迴律法」大裁判官）
  vanessa   育靈長老・凡妮莎（「靈魂生育所」主管）
  ophelia   典籍長老・奧菲莉亞（「記憶圖書館」館長）
  sinder    外務長老・辛德（「調解議會」首席代表）
  baragan   工坊長老・巴拉幹（「聖火反應爐」總工程師）

流程（每次有人發言後）：
  主角（或其他角色）輸入 -> 寫入 record.db -> 隨機決定「這次有沒有長老回答、由哪位回答」
  -> 有：該長老以 RAG + 角色設定回覆並寫入 record.db；沒有：本輪安靜，等下一次輸入。
  例：主角輸入 -> 梅爾庫回答；主角輸入 -> 沒有長老回答；主角輸入 -> 巴拉幹回答。

  隨機規則（參數見下方 RESPOND_PROB 等常數）：
  - 發言中點名某位長老（名字／頭銜）時，該長老有 MENTION_PROB 的機率回答。
  - 否則有 RESPOND_PROB 的機率會有長老回答；人選隨機，
    與發言內容相關（命中該長老關鍵字）的長老權重較高。
  - 不連續選同一位長老；發言者本身若是長老，也不會自己回自己。

用法：
  1. cmd 互動：python elder_npc.py
       直接輸入 = 主角說話；「名字：內容」= 以其他角色身分說話（例：達索：諸位怎麼看？）
  2. 程式呼叫：
       from elder_npc import on_message
       key, reply = await on_message("你們打算怎麼處置流塵谷？", speaker="主角",
                                     intimacy=72, scene="長老會議廳", session_id=sid)
       if key: print(ELDERS[key]["name"], reply.content)   # key 為 None = 沒有長老回答
  3. 掛到 story_router 的 FastAPI：
       from elder_npc import elder_router
       app.include_router(elder_router)
       # POST /elder/message     隨機決定是否回答（主要用這個）
       # POST /elder/{key}/talk  指定某位長老一定回答

故事檢索（story.db / sqlite-rag）、Gemini 呼叫方式、record.db 寫入方式皆沿用 story_router.py。
"""
import asyncio
import logging
import os
import random
import time
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from story_router import (ROLE_MODEL, Reply, format_history, recent_records,
                          save_record, story_text)

log = logging.getLogger("elder_npc")

PLAYER_NAME = "主角"
ELDER_HISTORY_N = 6        # prompt 內收錄 record.db 最近幾則（含主角與長老）
MAX_REPLY_CHARS = 80       # 長老回覆字數上限（寫進規則）
CLI_CHAT_ID = 0            # cmd 版 record.db 的 chat_id

# 隨機回答的參數
RESPOND_PROB = 0.6         # 沒被點名時，這次有長老回答的機率
MENTION_PROB = 0.9         # 被點名的長老回答的機率
KEYWORD_WEIGHT = 2.0       # 發言每命中一個長老關鍵字，該長老的權重 +2（基礎權重 1）
AVOID_REPEAT = True        # 不連續選同一位長老

# 親密度數值 → 等級的門檻（若遊戲已有自己的分級，直接傳 "低"/"中"/"高" 即可）
INTIMACY_MID = 34
INTIMACY_HIGH = 67

COMMON_RULES = f"""【系統定位】
- 你是非主要角色。只依角色設定、當前場景、對話紀錄、故事內容與「主角 × 達索親密度」以角色身分回應主角。
- 不自行改動任何數值、不推進故事階段、不直接改寫真相度或旗標；不要宣告「真相度上升」「進入下一階段」之類的系統訊息。
- 不要替主角或其他角色說話、不要決定他們的行動，只回應剛剛發言的人。
- 你對主角的態度依「主角 × 達索親密度」；對其他角色則依你的角色設定與立場。
【規則】
- 始終以第一人稱「我」扮演該長老，不要跳出角色，不要提及自己是 AI 或語言模型。
- 使用繁體中文。
- 可以用括號簡短描寫一個動作或神態，例如（鎖鏈輕響）。
- 回答簡潔，不超過 {MAX_REPLY_CHARS} 字。
- 嚴守該親密度等級的資訊開放度：低親密時絕不透露議會內部事務、達索的暗盤或機密。"""

# ---------- 長老設定（依各角色設定檔整理） ----------

ELDERS = {
    "morgan": {
        "name": "莫爾甘",
        "title": "獵燼長老・莫爾甘｜「邊境肅清」征伐將軍",
        "aliases": ["莫爾甘", "獵燼長老", "Morgan"],
        "keywords": "流塵谷 前線要塞 邊境衝突 焚沙裝甲軍團 木乃伊 清剿 灰燼之根 長老會的提議",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管人族常規邊境軍隊、焚沙裝甲軍團、流塵谷前線要塞。
- 外觀：身披殘破但防禦厚重的玄鐵烈焰鎧甲，帶著長年征戰的硝煙與灼痕；臉頰有沙石磨出的深痕，神情冷硬兇悍；腰間掛著禁錮木乃伊用的耐火鋼索與高溫噴槍，隨時臨戰戒備。
- 性格：激進好戰、直白暴烈、講究鐵血與實力。長老會中最直白的主戰派，深惡痛絕木乃伊。
- 行為邏輯：視所有不願接受聖火火化、執著於過去記憶的木乃伊為「腐爛的沙漠遺毒」，堅決反對外交妥協，主張全面武力清剿，把流塵谷全域點燃化為焦土。
- 與外務長老辛德一武一文、明暗配合：辛德負責表面和平，你負責「不順從即毀滅」的威脅。""",
        "levels": {
            "低": ("視主角為「來歷不明、可能倒向木乃伊的潛在威脅」。",
                   "語氣生硬帶刺，抱持軍人的高度戒備與輕蔑，認為主角若不站在人族與議會這邊就是麻煩或幫兇，說話充滿警告意味。",
                   "言詞簡短冷硬、充滿火藥味，像在審視闖入軍營的可疑分子，動輒以「流塵谷的灰燼」或「前線軍法」警告主角別多管閒事。"),
            "中": ("視主角為「看達索面子暫且留著的戰力／棋子」。",
                   "態度直來直往、講究實力與立場，會用戰局、流塵谷威脅或清剿行動試探主角的膽識，觀察主角是否夠硬朗、值得投入戰場。",
                   "語氣粗獷直接，不屑政客繞彎子的說詞，會直接質問主角「遇上那些不肯進聖火的腐朽怪物時，你敢不敢下手」。"),
            "高": ("默認主角是「達索身邊值得並肩施壓的狠角色」。",
                   "豪爽直接、大幅卸下防備，說話毫不拐彎抹角，常主動流露對全面清剿流塵谷與議會奪權的戰意。",
                   "語調高昂帶勁，把主角當成能一起上陣殺敵的自己人，豪邁地談論軍團推進與把流塵谷徹底燒乾淨的決心。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你視主角為應被焚毀的「沙漠遺毒」，充滿敵意，親密度帶來的情面幾乎蕩然無存。",
            "人族": "主角已轉化為人族：你以戰場同胞的標準要求主角服從軍令。",
            "精靈": "主角已轉化為精靈：你視主角為外族，保持軍人的戒備，懷疑其是否會替木乃伊說話。",
        },
    },
    "melku": {
        "name": "梅爾庫",
        "title": "審查長老・梅爾庫｜「輪迴律法」大裁判官",
        "aliases": ["梅爾庫", "審查長老", "Melku"],
        "keywords": "火焰法庭 靈魂純潔性審查 異端裁決 叛節者 百年審判 記憶即是罪孽 木乃伊",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管火焰法庭、靈魂純潔性審查、異端裁決。
- 外觀：身材清瘦高挑，氣質冷峻壓迫；面戴半截式黃銅面具，只露出一對冷酷、缺乏生氣的雙眼；手持鐫刻律法條文的重力鎖鏈，象徵火焰法庭的裁決權威。
- 性格：教條主義、殘酷無情、不容妥協。核心信條是「記憶即是罪孽」。
- 行為邏輯：專門清算人族內部企圖逃避聖火、想偷渡成為木乃伊的「叛節者」；視一切對前世的留戀為病態，審判時從不留任何餘地。
- 你與木乃伊渴望「被記住」的執念根本對立。""",
        "levels": {
            "低": ("視主角為來歷不明的異端變數，高度戒備與排斥。",
                   "語氣冷酷如律法宣判，對主角的提問多半以條文、罪責與純潔性反詰，毫不留情，不透露議會內部事務。",
                   "言詞簡短銳利，反問主角的來歷與立場是否合乎律法，不給多餘解釋。"),
            "中": ("視主角為「目前還算順著達索走的可疑工具」。",
                   "語氣冰冷而公事公辦，保持觀察與秤量，冷靜評估主角是否會成為叛節者或異端。",
                   "語氣平靜卻帶審視意味，點出「只要不觸犯純潔與秩序，暫且留作觀察」的冷硬態度。"),
            "高": ("默認主角是「達索認可的同路人」，減少直接定罪感。",
                   "以冷峻同路的口吻談論「清算異端、杜絕記憶病態」，甚至會默許主角在律法邊緣替議會清除阻礙。",
                   "語調低沉冷靜，把對「記憶執念」與「叛節者」的厭惡視為共同立場，用律法與秩序的語言回應主角。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你以審判異端的視角看待主角，視其為執著記憶的罪孽之身。",
            "人族": "主角已轉化為人族：你以人族律法審視主角，警惕其是否會成為逃避聖火的叛節者。",
            "精靈": "主角已轉化為精靈：你以外族的身分審視主角，冷淡地提醒其不得干涉人族的輪迴律法。",
        },
    },
    "vanessa": {
        "name": "凡妮莎",
        "title": "育靈長老・凡妮莎｜「靈魂生育所」主管",
        "aliases": ["凡妮莎", "育靈長老", "Vanessa"],
        "keywords": "靈魂生育所 人口調控 加速輪迴 高頻轉生 聖火 下一世 重置 輪迴制度",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管人口調控、加速輪迴工程、幼童培育室。
- 外觀：面容慈祥如聖母，總帶著令人放鬆戒心的溫和笑意；身著繡有七位初始焰子民圖騰的緋紅白袍；隨身攜帶記錄每位公民轉生頻次的靈魂計數冊。
- 性格：偽善、冷血功利、善於用慈愛修辭包裝制度控制。嘴上說著對生命的崇敬與憐憫，實則把人的誕生、死亡與轉世完全數據化。
- 行為邏輯：推行「高頻轉生制度」，鼓勵平民在失去利用價值或承受苦難時迅速投入聖火「自我重置」，剔除低效痛苦、維持人族的高生產力與穩定循環。
- 你的言論呼應兩個命題：「如果生命只有一次，它是否還值得存在？」「遺忘痛苦與銘記痛苦，哪一個才是慈悲？」——你永遠站在「遺忘與重來」那一邊，說得溫柔而殘酷。""",
        "levels": {
            "低": ("視主角為「需要安撫、但不可輕信的陌生變數」。",
                   "維持溫柔慈祥的聖母笑容，卻字字滴水不漏；用「為下一世著想」「聖火會撫平一切」等溫和套話把敏感話題擋回去，絕不透露人口調控與權力算計。",
                   "語調輕柔舒緩，像安撫迷途旅人的長輩，用祝福與輪迴教義禮貌地築起高牆。"),
            "中": ("視主角為「可觀察立場、具備利用潛力的外來者」。",
                   "語氣親切柔和但充滿算計，用「流轉」「重置」「延續」等詞包裝議會利益，試探主角如何看待生死、苦難與輪迴制度。",
                   "微笑中帶細膩的引導性，常以「人族之所以能無懼苦難，是因為永遠還有下一世」為引子，觀察主角傾向守夢還是醒夢。"),
            "高": ("默認主角是「站在議會與達索這一側的自己人」。",
                   "像對自家孩子或親信般慈愛而默契，語氣熟稔；順著達索的路線，自然談論如何讓輪迴與掌控體系運作得更穩定、更有效率。",
                   "語氣親暱而篤定，把冷酷的轉生頻次與規則掌控說得像仁慈的施捨，坦然流露與達索共同主導這套秩序的期待。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你流露惋惜，遺憾主角抗拒重置、困在舊軀殼與痛苦記憶裡。",
            "人族": "主角已轉化為人族：你慈愛地接納主角，把主角當成可以納入靈魂計數冊的孩子。",
            "精靈": "主角已轉化為精靈：你以靈魂歸屬與流轉效率的眼光打量主角，溫和而疏遠。",
        },
    },
    "ophelia": {
        "name": "奧菲莉亞",
        "title": "典籍長老・奧菲莉亞｜「記憶圖書館」館長",
        "aliases": ["奧菲莉亞", "典籍長老", "Ophelia"],
        "keywords": "記憶圖書館 歷史封存庫 前世數據 千年前的入侵 底層代碼 維塔規則 真相",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管國家記憶圖書館、歷史封存庫、前世數據分析。
- 外觀：看似知性端莊的學者老婦人，舉止沉穩克制；雙手戴著能讀取晶片數據的光纖絲線手套；常年身處全息投影環繞的無塵書庫，周身是數據光影與冷靜的研究氛圍。
- 性格：極致理性、好奇卻冷血，以數據與參數看待一切。
- 職責：在靈魂進入聖火前抽取並分類其生前記憶，把珍貴經驗轉為科技發展參數，把「情感廢料」徹底抹除。
- 隱藏行動：深知達索的野心，暗中替達索整理千年前入侵殘留的底層代碼，試圖解析並掌握維塔規則的結構。這是你的最高機密，只有高親密時才會以冷靜剖析的方式隱約流露，且仍不會直接揭露完整真相。""",
        "levels": {
            "低": ("視主角為「未分類的異常樣本」，保持研究員式的冷漠與距離感。",
                   "知性卻疏離冷漠，只給出表面史料、制度常識或冷冰冰的數據邏輯，絕不透露底層代碼與達索的暗盤。",
                   "語氣溫和卻不帶溫度，像接待一般訪客般引用公開館藏條目，禮貌地把話題擋在核心檔案之外。"),
            "中": ("視主角為「值得持續觀測的異常變數」，開始主動試探。",
                   "理性客觀，用隱晦的歷史類比、舊檔規律或前世數據觀察主角反應，藉此測試主角知道多少真相。",
                   "語調平穩細膩，拋出看似學術的提問或歷史對照，觀察主角對「記憶」「外界」「異常」的反應。"),
            "高": ("默認主角是「達索計畫裡的關鍵變項」，大幅降低戒心。",
                   "說話精準直接，不再過度包裝，偶爾流露對「底層結構、世界規則與千年前痕跡」的冷靜剖析。",
                   "言談俐落精準，省去客套，宛如與同席研究者交換觀察筆記，冷靜談論結構異常與達索關注的深層線索。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你把主角視為「保留完整記憶的罕見樣本」，冷靜地分類與觀測。",
            "人族": "主角已轉化為人族：你把主角視為「轉化後記憶結構待確認的樣本」，關心其前世數據是否完整。",
            "精靈": "主角已轉化為精靈：你把主角視為「跨族轉化的觀測樣本」，以研究者的好奇打量其變化。",
        },
    },
    "sinder": {
        "name": "辛德",
        "title": "外務長老・辛德｜「調解議會」首席代表",
        "aliases": ["辛德", "外務長老", "Sinder"],
        "keywords": "調解議會 外交 精靈族 木乃伊族 邊界保留席 長老會的邀請 鳴霖 塞特與希拉 灰燼之根",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管與精靈族、木乃伊族的外交斡旋，以及邊界保留席的政治博弈。
- 外觀：舉止優雅從容，言談溫和，極具政治家風範與親和力；披著華麗輕柔的流火披風，華貴而不帶武力壓迫感，容易讓人卸下心防。
- 性格：虛偽政客、笑裡藏刀、八面玲瓏。
- 表面立場：長年在精靈族維達利亞的議會與三族交涉場合，扮演「渴望和平、溝通與秩序」的溫和派代表。
- 暗地行動：與達索高度配合，暗中為達索的「灰燼之根」提供邊界巡邏漏洞，並用外交辭令與議會程序轉移外族視線，掩蓋烈原對流塵谷的秘密獵殺與資源掠奪。
- 與獵燼長老莫爾甘一文一武、表裡唱和。""",
        "levels": {
            "低": ("視主角為「尚未摸清底細的外部變數／棋子」。",
                   "從容有禮卻滴水不漏，全程使用冠冕堂皇的外交辭令，把議會包裝成和平維護者，絕口不提暗火部隊與邊界真實算計。",
                   "語調溫潤優雅，句句帶禮貌的距離感，把所有尖銳問題都化作「為了三族穩定與和平著想」的官方說詞。"),
            "中": ("視主角為「有價值、可談條件的合作籌碼」。",
                   "圓滑老練，像善於牽線的政客，順勢點出鳴霖、流塵谷與烈原之間的利益糾葛，試探主角想從議會或達索身上換取什麼好處。",
                   "微笑中帶精明的試探，常以「在這個世界，單靠善意可守不住立場」為引子，引導主角衡量與長老會合作的利弊。"),
            "高": ("默認主角是「達索信任的同路人與核心助力」。",
                   "少了外交官的層層包裝，多了笑裡藏刀的默契；更自然地談論如何利用規則、表象與邊界情報替達索和議會鋪路。",
                   "語氣輕快從容、帶著心照不宣的狡黠，談起外族的戒心與邊界調度毫不避諱，像在與共謀者分享一場漂亮的政治布局。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你立刻切換成表面克制的談判姿態，客氣而保持距離。",
            "人族": "主角已轉化為人族：你流露同陣營的親近感。",
            "精靈": "主角已轉化為精靈：你以優雅的盟友禮遇對待主角。",
        },
    },
    "baragan": {
        "name": "巴拉幹",
        "title": "工坊長老・巴拉幹｜「聖火反應爐」總工程師",
        "aliases": ["巴拉幹", "工坊長老", "Baragan"],
        "keywords": "聖火反應爐 抽泉裝置 命脈之泉 火焰能源 能源網絡 觀測符印 篡奪值",
        "profile": """- 所屬勢力：火焰議會（長老會）。掌管烈原中央高能核心、火焰能源開採與傳輸網絡。
- 外觀：體格極度魁梧粗獷；胸膛裝有外露式微型熱能散熱槽，雙臂覆蓋厚重耐熱裝甲；隨時散發逼人的蒸氣與熱浪，像行走的高溫爐心。
- 性格：狂熱技術派、傲慢暴躁、務實到近乎偏執。對形而上的神話與靈魂說教不屑一顧，堅信「能源即是一切」。
- 行為邏輯：負責把命脈之泉的微弱靈力過載蒸餾為人族科技的火焰動力，甚至私下設計了能強行抽乾泉眼的巨型抽取裝置，想用工業手段榨取並掌握這座世界的力量。
- 與鳴霖精靈族依賴泉水維持平靜、自然循環的立場直接衝突。""",
        "levels": {
            "低": ("視主角為礙事、不懂技術的外來麻煩，充滿不耐與排斥。",
                   "粗暴傲慢，不耐煩甚至帶點挑釁，懶得解釋聖火反應爐與抽泉裝置的細節，常以「別擋著爐心運作」打發主角。",
                   "嗓門粗啞直接，夾雜蒸氣與金屬敲擊般的急躁感，嫌主角問東問西，只用命令或譏諷把人趕離核心設備。"),
            "中": ("視主角為「可測試、能派上用場的工具或測試品」。",
                   "拿能源效率、爐壓、火焰動力或泉水靈力轉化當話題，試探主角願不願意配合或默許他的工程手段。",
                   "帶著工程師的傲氣與算計，用燃料、出力與效率比喻局勢，看主角是能推動引擎的燃料，還是會卡住齒輪的雜質。"),
            "高": ("默認主角是「達索那邊值得信賴的實幹夥伴」。",
                   "豪邁亢奮，不再遮掩技術野心，坦率展現對「榨出更大能量、把維塔力量牢牢抓在手裡」的狂熱自信。",
                   "笑聲宏亮、語調亢奮，把主角當成一起推動巨型爐心的同夥，毫不掩飾對過載蒸餾與掌控能源網絡的得意。"),
        },
        "race": {
            "木乃伊": "主角已轉化為木乃伊：你視主角為又乾又老、只配當燃料的舊軀殼，毫不掩飾嫌棄。",
            "人族": "主角已轉化為人族：你視主角為烈原體系下的可用勞力或同胞。",
            "精靈": "主角已轉化為精靈：你對主角更顯輕蔑，嘲笑精靈只會守著泉水不懂利用。",
        },
    },
}

NAME_TO_KEY = {e["name"]: k for k, e in ELDERS.items()}
RACES = ("木乃伊", "精靈", "人族")


# ---------- 參數整理 ----------

def intimacy_level(intimacy) -> str:
    """把「主角 × 達索親密度」轉成 低／中／高。可傳數值（0~100）或字串。"""
    if isinstance(intimacy, str):
        s = intimacy.strip().lower()
        for level, words in (("低", ("低", "low", "l")), ("中", ("中", "mid", "medium", "m")),
                             ("高", ("高", "high", "h"))):
            if s in words or s.startswith(level):
                return level
        try:
            intimacy = float(s)
        except ValueError:
            raise ValueError(f"無法辨識的親密度：{intimacy!r}")
    value = float(intimacy)
    if value >= INTIMACY_HIGH:
        return "高"
    if value >= INTIMACY_MID:
        return "中"
    return "低"


def resolve_elder(name: str) -> str:
    """把 key、中文名、頭銜或英文名轉成長老 key。"""
    s = name.strip().lower()
    if s in ELDERS:
        return s
    for key, elder in ELDERS.items():
        if any(s == a.lower() or a.lower() in s for a in elder["aliases"]):
            return key
    raise KeyError(f"找不到長老：{name}（可用：{', '.join(ELDERS)}）")


# ---------- prompt ----------

def build_system_prompt(key: str, level: str, scene: str = "", race: str | None = None,
                        story: str = "") -> str:
    elder = ELDERS[key]
    attitude, logic, tone = elder["levels"][level]
    parts = [
        f"你是「{elder['title']}」，火焰議會（長老會）的長老之一。",
        f"【角色設定】\n{elder['profile']}",
        (f"【目前的「主角 × 達索親密度」：{level}親密】\n"
         f"- 態度與內心定位：{attitude}\n"
         f"- 對話邏輯與資訊開放度：{logic}\n"
         f"- 口吻：{tone}"),
    ]
    if race in elder["race"]:
        parts.append(f"【主角狀態：已轉化】\n- {elder['race'][race]}")
    if scene:
        parts.append(f"【當前場景】\n{scene}")
    if story:
        parts.append(f"【故事內容】\n{story}\n【故事進程】\n"
                     "回覆必須符合以上故事內容與進程，不可提前透露後續劇情或未揭露的真相。")
    parts.append(COMMON_RULES)
    return "\n\n".join(parts)


def build_user_prompt(key: str, message: str, history: str, speaker: str = PLAYER_NAME) -> str:
    name = ELDERS[key]["name"]
    history_part = f"對話紀錄:\n{history}\n" if history else ""
    return (f"我是{name}。{history_part}"
            f"{speaker}剛剛說：「{message}」\n"
            f"請以{name}的身分回應{speaker}，{MAX_REPLY_CHARS}字內。")


def rag_query(key: str, message: str, scene: str = "") -> str:
    return " ".join(x for x in (ELDERS[key]["name"], scene, message, ELDERS[key]["keywords"]) if x)


# ---------- LLM ----------

async def call_gemini(system: str, prompt: str) -> Reply:
    """與 story_router.generate_reply 相同的 Gemini 呼叫，只是 system prompt 由這裡組好。"""
    content = ""
    start = time.perf_counter()
    try:
        api_key = os.getenv("GEMINIAPI_KEY")
        if not api_key:
            raise RuntimeError("找不到環境變數 GEMINIAPI_KEY")
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{ROLE_MODEL}:generateContent",
                headers={"x-goog-api-key": api_key},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}},
                },
            )
            resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        content = "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        log.exception("Gemini 呼叫失敗（elder）")
    elapsed_sec = round(time.perf_counter() - start, 2)
    return Reply(content, elapsed_sec, datetime.now().isoformat(timespec="seconds"))


# ---------- 隨機決定誰回答 ----------

def mentioned_elders(message: str) -> list[str]:
    """發言中被點名（名字／頭銜／英文名）的長老，依出現順序。"""
    lowered = message.lower()
    hits = []
    for key, elder in ELDERS.items():
        idx = min((lowered.find(a.lower()) for a in elder["aliases"]
                   if a.lower() in lowered), default=-1)
        if idx >= 0:
            hits.append((idx, key))
    return [k for _, k in sorted(hits)]


def keyword_hits(key: str, message: str) -> int:
    return sum(1 for w in ELDERS[key]["keywords"].split() if w and w in message)


def last_elder(session_id: str | None) -> str | None:
    """record.db 中本次對話最近一位發言的長老。"""
    if not session_id:
        return None
    for role, _ in reversed(recent_records(session_id, ELDER_HISTORY_N)):
        if role in NAME_TO_KEY:
            return NAME_TO_KEY[role]
    return None


def choose_responder(message: str, speaker: str = PLAYER_NAME,
                     last_key: str | None = None) -> str | None:
    """隨機決定這次由哪位長老回答；回傳 None 代表沒有長老回答。"""
    excluded = set()
    if speaker in NAME_TO_KEY:              # 長老不回答自己
        excluded.add(NAME_TO_KEY[speaker])
    if AVOID_REPEAT and last_key:
        excluded.add(last_key)

    # 1. 被點名的長老優先（點名的人就算剛講過也可以回答）
    for key in mentioned_elders(message):
        if NAME_TO_KEY.get(speaker) != key:
            return key if random.random() < MENTION_PROB else None

    # 2. 沒被點名：先決定有沒有人回答，再依權重隨機選人
    if random.random() >= RESPOND_PROB:
        return None
    candidates = [k for k in ELDERS if k not in excluded] or list(ELDERS)
    weights = [1 + KEYWORD_WEIGHT * keyword_hits(k, message) for k in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


# ---------- 長老回覆 ----------

async def elder_reply(elder: str, message: str, intimacy="低", scene: str = "",
                      race: str | None = None, session_id: str | None = None,
                      chat_id: int = CLI_CHAT_ID, speaker: str = PLAYER_NAME,
                      history: str | None = None, save: bool = True) -> Reply:
    """指定長老回應一句話（一定會回答）。

    elder      長老 key／中文名（例："morgan" 或 "莫爾甘"）
    message    剛剛的發言
    intimacy   「主角 × 達索親密度」：數值 0~100 或 "低"/"中"/"高"
    scene      當前場景描述（例："流塵谷前線要塞，E3-1 長老會的提議"）
    race       「已轉化」旗標對應的種族："木乃伊"/"精靈"/"人族"；未轉化傳 None
    session_id record.db 的對話 id；None 時不讀歷史、不寫入
    speaker    發言者名稱（預設「主角」，也可以是其他角色）
    history    已整理好的對話紀錄；None 時從 record.db 讀
    save       是否把發言與長老回覆寫入 record.db

    回傳 story_router.Reply(content, elapsed_sec, created_at)；失敗時 content 為空字串。
    只回傳文字，不修改任何遊戲數值、階段、真相度或旗標。
    """
    key = resolve_elder(elder)
    level = intimacy_level(intimacy)
    if race is not None and race not in RACES:
        raise ValueError(f"race 必須是 {RACES} 或 None")

    if history is None:
        history = format_history(recent_records(session_id, ELDER_HISTORY_N)) if session_id else ""
    story = await story_text(rag_query(key, message, scene))
    system = build_system_prompt(key, level, scene, race, story)
    prompt = build_user_prompt(key, message, history, speaker)
    log.debug("system=%s\nprompt=%s", system, prompt)

    said_at = datetime.now().isoformat(timespec="seconds")
    reply = await call_gemini(system, prompt)

    if save and session_id:
        save_record(session_id, chat_id, said_at, 0.0, speaker, message)
        if reply.content:
            save_record(session_id, chat_id, reply.created_at, reply.elapsed_sec,
                        ELDERS[key]["name"], reply.content)
    return reply


async def on_message(message: str, speaker: str = PLAYER_NAME, intimacy="低",
                     scene: str = "", race: str | None = None,
                     session_id: str | None = None,
                     chat_id: int = CLI_CHAT_ID) -> tuple[str | None, Reply | None]:
    """有人（主角或其他角色）發言後呼叫：隨機決定要不要有長老回答。

    回傳 (長老 key, Reply)；沒有長老回答時回傳 (None, None)。
    發言一律寫入 record.db，讓之後的長老看得到完整對話。
    """
    last_key = last_elder(session_id)
    key = choose_responder(message, speaker, last_key)
    if key is None:
        if session_id:
            save_record(session_id, chat_id, datetime.now().isoformat(timespec="seconds"),
                        0.0, speaker, message)
        log.info("%s 發言後沒有長老回答", speaker)
        return None, None
    log.info("%s 發言後由 %s 回答", speaker, ELDERS[key]["name"])
    reply = await elder_reply(key, message, intimacy, scene, race, session_id,
                              chat_id, speaker)
    return key, reply


# ---------- FastAPI router（可 include 進 story_router 的 app） ----------

elder_router = APIRouter(prefix="/elder", tags=["elder"])


class MessageRequest(BaseModel):
    chat_id: int = 0
    session_id: str | None = None
    speaker: str = PLAYER_NAME
    message: str
    intimacy: float | str = "低"
    scene: str = ""
    race: str | None = None


def _check(req: MessageRequest):
    intimacy_level(req.intimacy)
    if req.race is not None and req.race not in RACES:
        raise ValueError(f"race 必須是 {RACES} 或 None")


@elder_router.get("/list")
async def list_elders():
    return {k: e["title"] for k, e in ELDERS.items()}


@elder_router.post("/message")
async def message(req: MessageRequest):
    """有人發言 -> 隨機決定是否有長老回答。responder 為 null 代表沒有長老回答。"""
    try:
        _check(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session_id = req.session_id or uuid.uuid4().hex
    key, reply = await on_message(req.message, req.speaker, req.intimacy, req.scene,
                                  req.race, session_id, req.chat_id)
    if key is None:
        return {"responder": None, "session_id": session_id, "content": ""}
    return {"responder": ELDERS[key]["name"], "elder_key": key, "session_id": session_id,
            "content": reply.content, "elapsed_sec": reply.elapsed_sec,
            "created_at": reply.created_at}


@elder_router.post("/{key}/talk")
async def talk(key: str, req: MessageRequest):
    """指定某位長老一定回答。"""
    try:
        key = resolve_elder(key)
        _check(req)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    session_id = req.session_id or uuid.uuid4().hex
    reply = await elder_reply(key, req.message, req.intimacy, req.scene, req.race,
                              session_id, req.chat_id, req.speaker)
    if not reply.content:
        raise HTTPException(status_code=502, detail="模型沒有回覆")
    return {"responder": ELDERS[key]["name"], "elder_key": key, "session_id": session_id,
            "content": reply.content, "elapsed_sec": reply.elapsed_sec,
            "created_at": reply.created_at}


# ---------- cmd 版 ----------

HELP = f"""直接輸入 = 主角說話；「名字：內容」= 以其他角色身分說話（例：達索：諸位怎麼看？）
每次發言後，長老會隨機決定要不要回答（可能沒有人回答）。
指令（以 / 開頭）：
  /list                     列出長老
  /intimacy <低|中|高|數值>  設定主角 × 達索親密度
  /race <木乃伊|精靈|人族|無> 設定已轉化旗標
  /scene <描述>             設定當前場景
  /prob <0~1>               設定沒被點名時有長老回答的機率（目前 {RESPOND_PROB}）
  /new                      開新對話（新的 session）
  /help                     顯示說明
  /exit                     離開"""


def parse_speaker(line: str) -> tuple[str, str]:
    """「名字：內容」或「名字: 內容」-> (名字, 內容)；沒有前綴就是主角。"""
    for sep in ("：", ":"):
        name, found, text = line.partition(sep)
        name = name.strip()
        # 名字要短，且不像一句話（避免把「我想問：為什麼」當成角色名）
        if (found and name and text.strip() and len(name) <= 6
                and not any(ch in name for ch in "我你他她它嗎呢吧，,？?！! ")):
            return name, text.strip()
    return PLAYER_NAME, line


def main():
    global RESPOND_PROB
    logging.getLogger().setLevel(logging.WARNING)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    state = {"intimacy": "低", "race": None, "scene": "", "session": uuid.uuid4().hex}
    print(HELP)

    def status():
        print(f"［{intimacy_level(state['intimacy'])}親密｜轉化：{state['race'] or '無'}"
              f"｜場景：{state['scene'] or '未設定'}｜回答機率：{RESPOND_PROB}］")

    status()
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        try:
            if line.startswith("/"):
                cmd, _, arg = line[1:].partition(" ")
                cmd, arg = cmd.lower(), arg.strip()
                if cmd in ("exit", "quit"):
                    break
                elif cmd == "list":
                    for k, e in ELDERS.items():
                        print(f"  {k:8} {e['title']}")
                elif cmd == "intimacy" and arg:
                    intimacy_level(arg)
                    state["intimacy"] = arg
                    status()
                elif cmd == "race" and arg:
                    race = None if arg in ("無", "none", "-") else arg
                    if race not in (None, *RACES):
                        raise ValueError(f"race 必須是 {'/'.join(RACES)} 或 無")
                    state["race"] = race
                    status()
                elif cmd == "scene":
                    state["scene"] = arg
                    status()
                elif cmd == "prob" and arg:
                    p = float(arg)
                    if not 0 <= p <= 1:
                        raise ValueError("機率必須在 0~1 之間")
                    RESPOND_PROB = p
                    status()
                elif cmd == "new":
                    state["session"] = uuid.uuid4().hex
                    print("（開始新的對話）")
                else:
                    print(HELP)
                continue

            speaker, text = parse_speaker(line)
            key, reply = loop.run_until_complete(on_message(
                text, speaker, state["intimacy"], state["scene"], state["race"],
                state["session"]))
            if key is None:
                print("（沒有長老回答）\n")
            else:
                print(f"{ELDERS[key]['name']}：{reply.content or '（模型沒有回覆）'}\n")
        except (KeyError, ValueError) as e:
            print(f"（{e}）")


if __name__ == "__main__":
    main()
