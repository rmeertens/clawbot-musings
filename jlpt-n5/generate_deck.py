#!/usr/bin/env python3
"""Parse JLPT N5 vocabulary from extracted PDF text and generate an Anki .apkg deck."""

import genanki
import re
import hashlib

CHAPTERS = [
    ("Ch 01: あびる–ちがう", [
    ("浴びる", "あびる", "abiru", "V1, VT", "to bathe; to bask in the sun, to shower"),
    ("危ない", "あぶない", "abunai", "ADJ-I", "dangerous; hazardous, perilous; in danger"),
    ("あちら", "", "achira", "N, UK", "over there; that way, that one; that person", "See also: あっち (acchi) — casual form"),
    ("あっち", "", "acchi", "N, UK", "over there; that way, that one; that person", "See also: あちら (achira) — polite form"),
    ("上げる", "あげる", "ageru", "V1, VT", "to give; to raise, to fly (a kite, etc.)"),
    ("赤", "あか", "aka", "N", "red; crimson, scarlet"),
    ("赤い", "あかい", "akai", "ADJ-I", "red"),
    ("飴", "あめ", "ame", "N", "(hard) candy; toffee"),
    ("雨", "あめ", "ame", "N", "rain"),
    ("あなた", "", "anata", "N, UK, POL", "you (referring to sb. of equal or lower status); dear"),
    ("姉", "あね", "ane", "N, HUM", "older sister; elder sister"),
    ("兄", "あに", "ani", "N, HUM", "older brother; elder brother"),
    ("あの", "", "ano", "ADJ-PN, UK", "that (sb or sthg far from both speaker and listener)"),
    ("洗う", "あらう", "arau", "V5U, VT", "to wash"),
    ("あれ", "", "are", "PN", "that (indicating sth away from both speaker and listener)"),
    ("ある", "", "aru", "V5R-I, VI, UK", "to be (usu. for inanimate objects); to exist, to live; to have; to be located"),
    ("歩く", "あるく", "aruku", "V5K, VI", "to walk"),
    ("朝", "あさ", "asa", "N-ADV, N-T", "morning"),
    ("朝御飯", "あさごはん", "asagohan", "N", "breakfast"),
    ("新しい", "あたらしい", "atarashii", "ADJ-I", "new"),
    ("暖かい", "あたたかい", "atatakai", "ADJ-I", "warm (usu. air temperature); mild, genial"),
    ("後", "あと", "ato", "N, ADJ-NO", "behind; rear, after, later; descendant; successor"),
    ("厚い", "あつい", "atsui", "ADJ-I", "thick; cordial, warm(-hearted); heavy; abundant"),
    ("暑い", "あつい", "atsui", "ADJ-I", "hot (weather, etc.); warm"),
    ("熱い", "あつい", "atsui", "ADJ-I", "hot (thing, feeling); fired up; ardent"),
    ("勉強", "べんきょう", "benkyō", "N, VS", "study"),
    ("便利", "べんり", "benri", "ADJ-NA", "convenient; handy, useful"),
    ("ボールペン", "", "bōrupen", "N", "ball-point pen"),
    ("帽子", "ぼうし", "bōshi", "N", "hat; cap"),
    ("ボタン", "", "botan", "N, UK", "button"),
    ("文章", "ぶんしょう", "bunshō", "N", "sentence; article, composition"),
    ("豚肉", "ぶたにく", "butaniku", "N, ADJ-NO", "pork"),
    ("明るい", "あかるい", "akarui", "ADJ-I", "bright; light, cheerful"),
    ("開ける", "あける", "akeru", "V1, VT", "to open (a door, etc.); to unwrap (e.g. parcel)"),
    ("秋", "あき", "aki", "N-T", "autumn; fall"),
    ("開く", "あく", "aku", "V5K, VI", "to open (e.g. doors); to open (e.g. business, etc.)"),
    ("甘い", "あまい", "amai", "ADJ-I, UK", "sweet; easy, permissive, indulgent"),
    ("あまり", "あんまり", "amari, anmari", "ADV, NA-ADJ", "not very (used with negative sentences), not much; remainder, rest"),
    ("あのう", "", "anō", "INT, UK", "um...; say, well, err... (hesitation sound)"),
    ("青", "あお", "ao", "N", "blue; green"),
    ("青い", "あおい", "aoi", "ADJ-I", "blue; green; pale; unripe, inexperienced"),
    ("アパート", "", "apāto", "ABBR", "apartment; apartment house"),
    ("あさって", "", "asatte", "N-ADV, N-T", "day after tomorrow"),
    ("足", "あし", "ashi", "N", "foot; leg; gait; pace"),
    ("明日", "あした", "ashita", "N-T", "tomorrow"),
    ("遊ぶ", "あそぶ", "asobu", "V5B, VI", "to play; to make a visit (esp. for pleasure); to do nothing"),
    ("あそこ", "", "asoko", "N, UK", "over there; there; that place, yonder"),
    ("頭", "あたま", "atama", "N", "head; brain, intellect, mind"),
    ("会う", "あう", "au", "V5U, VI", "to meet; to encounter"),
    ("晩", "ばん", "ban", "N-ADV, N-T", "evening; (counter for) nights"),
    ("番号", "ばんごう", "bangō", "N", "number; series of digits"),
    ("晩御飯", "ばんごはん", "bangohan", "N", "dinner; evening meal"),
    ("バス", "", "basu", "N", "bus; bath; bass"),
    ("バター", "", "batā", "N", "butter"),
    ("ベッド", "", "beddo", "N", "bed"),
    ("病院", "びょういん", "byōin", "N", "hospital"),
    ("病気", "びょうき", "byōki", "N, ADJ-NO", "illness; disease, sickness"),
    ("茶色", "ちゃいろ", "chairo", "N", "light brown; tawny"),
    ("茶わん", "ちゃわん", "chawan", "N", "rice bowl; tea cup, teacup"),
    ("父", "ちち", "chichi", "N, HUM", "father"),
    ("違う", "ちがう", "chigau", "V5U, VI", "to differ (from); to vary; to not match the correct (answer, etc.)"),
    ]),
    ("Ch 02: ふるい–ちず", [
    ("古い", "ふるい", "furui", "ADJ-I", "old (not used for people); aged, ancient, stale, outmoded"),
    ("二人", "ふたり", "futari", "N", "two people; two persons, pair, couple"),
    ("二つ", "ふたつ", "futatsu", "N", "two"),
    ("封筒", "ふうとう", "fūtō", "N", "envelope"),
    ("太い", "ふとい", "futoi", "ADJ-I", "fat; thick; deep (of a voice); daring"),
    ("フォーク", "", "fōku", "N", "fork"),
    ("吹く", "ふく", "fuku", "V5K", "to blow (wind, etc.); to breeze; to play (wind instruments); to spout"),
    ("服", "ふく", "fuku", "N, N-SUF", "clothes (esp. Western clothes)"),
    ("風呂", "ふろ", "furo", "N", "bath; bathtub; bathroom, bathhouse"),
    ("降る", "ふる", "furu", "V5R, VI", "to precipitate; to fall (e.g. rain)"),
    ("映画", "えいが", "eiga", "N", "movie; film"),
    ("映画館", "えいがかん", "eigakan", "N", "movie theater; cinema"),
    ("英語", "えいご", "eigo", "N", "English (language)"),
    ("駅", "えき", "eki", "N", "station"),
    ("鉛筆", "えんぴつ", "enpitsu", "N", "pencil"),
    ("エレベーター", "", "erebētā", "N", "elevator; lift"),
    ("フィルム", "", "firumu", "N", "roll of film"),
    ("どうして", "", "dōshite", "ADV, INT, UK", "for what reason; why?, how, in what way"),
    ("土曜日", "どようび", "doyōbi", "N-ADV, N-T", "Saturday"),
    ("どうぞ", "", "dōzo", "ADV", "please; kindly; by all means"),
    ("絵", "え", "e", "N, N-SUF", "picture; drawing, painting, sketch"),
    ("ええ", "", "ē", "INT", "yes; right; well, um...; huh?"),
    ("動物", "どうぶつ", "dōbutsu", "N", "animal"),
    ("どちら", "", "dochira", "N, UK", "which way; which direction, where", "See also: どっち (docchi) — casual form"),
    ("どっち", "", "docchi", "N, UK", "which way; which direction, where", "See also: どちら (dochira) — polite form"),
    ("どこ", "", "doko", "N, UK", "where; what place"),
    ("どうも", "", "dōmo", "INT, ABBR", "thanks; very (sorry)"),
    ("どなた", "", "donata", "N, UK, HON", "who"),
    ("どの", "", "dono", "ADJ-PN, UK", "which; what (way)"),
    ("どれ", "", "dore", "N, UK", "which (of three or more)"),
    ("電車", "でんしゃ", "densha", "N", "(electric) train"),
    ("電話", "でんわ", "denwa", "N, VS", "telephone"),
    ("デパート", "", "depāto", "N, ABBR", "department store"),
    ("出る", "でる", "deru", "V1, VI", "to appear; to come forth; to leave; to answer (the phone or door)"),
    ("どう", "", "dō", "ADV, UK", "how; in what way, how about", "See also: いかが (ikaga) — polite form"),
    ("いかが", "", "ikaga", "ADV, UK, HON", "how; in what way, how about", "See also: どう (dō) — casual form"),
    ("ドア", "", "doa", "N", "western style door"),
    ("出口", "でぐち", "deguchi", "N", "exit; gateway, way out, outlet"),
    ("出かける", "でかける", "dekakeru", "V1, VI", "to go out (e.g. on an excursion); to depart, to set out"),
    ("出来る", "できる", "dekiru", "V1, VI, UK", "to be able to; to be up to the task; to be ready, to be completed"),
    ("でも", "", "demo", "CONJ", "but; however, though, still, yet, even so"),
    ("電気", "でんき", "denki", "N", "electricity; (electric) light"),
    ("電気ストーブ", "でんきストーブ", "denki sutōbu", "N", "electric heater"),
    ("だんだん", "", "dandan", "N, ADV-TO, ADV", "gradually; by degrees"),
    ("誰", "だれ", "dare", "N", "who"),
    ("誰か", "だれか", "dareka", "N, UK", "somebody; someone"),
    ("出す", "だす", "dasu", "V5S, VT", "to take out; to reveal, to show; to submit; to send"),
    ("では", "", "de wa", "CONJ, INT", "with that; then, well, so"),
    ("ちょうど", "", "chōdo", "ADJ-NA, ADV, N, UK", "exactly; just, right"),
    ("ちょっと", "", "chotto", "ADV, UK", "somewhat; easily, readily, rather; just a minute"),
    ("台所", "だいどころ", "daidokoro", "N, ADJ-NO", "kitchen"),
    ("大学", "だいがく", "daigaku", "N", "university; college"),
    ("大丈夫", "だいじょうぶ", "daijōbu", "ADJ-NA, ADV, N", "all right; safe, OK"),
    ("大好き", "だいすき", "daisuki", "ADJ-NA, N", "very likable; favorite, lovable, like very much"),
    ("小さい", "ちいさい", "chiisai", "ADJ-I", "little; small, tiny"),
    ("小さな", "ちいさな", "chiisana", "ADJ-PN", "little; small, tiny"),
    ("近い", "ちかい", "chikai", "ADJ-I", "near; close, short (distance)"),
    ("近く", "ちかく", "chikaku", "N-ADV, N", "near; neighborhood; nearly, close to; shortly, soon"),
    ("地下鉄", "ちかてつ", "chikatetsu", "N", "underground train; subway"),
    ("地図", "ちず", "chizu", "N", "map"),
    ]),
    ("Ch 03: ひくい–げんかん", [
    ("低い", "ひくい", "hikui", "ADJ-I", "low (height, tone, rank, degree, cost, etc.); short"),
    ("暇", "ひま", "hima", "ADJ-NA, N", "free time; spare time, leisure"),
    ("広い", "ひろい", "hiroi", "ADJ-I", "spacious; vast, wide"),
    ("昼", "ひる", "hiru", "N-ADV, N-T", "noon; midday; daytime; lunch"),
    ("昼御飯", "ひるごはん", "hirugohan", "N", "lunch; midday meal"),
    ("人", "ひと", "hito", "N", "person; man; human being, mankind"),
    ("下手", "へた", "heta", "ADJ-NA, N", "unskillful; poor, awkward; imprudent"),
    ("部屋", "へや", "heya", "N", "room; (one's own) place, apartment"),
    ("左", "ひだり", "hidari", "N", "left; left-hand side"),
    ("東", "ひがし", "higashi", "N", "east"),
    ("飛行機", "ひこうき", "hikōki", "N", "airplane; aeroplane, aircraft"),
    ("引く", "ひく", "hiku", "V5K, VI, VT", "to pull; to draw (attention etc.), to draw back"),
    ("弾く", "ひく", "hiku", "V5K", "to play (an instrument with strings, including piano)"),
    ("二十歳", "はたち", "hatachi", "N", "20 years old"),
    ("働く", "はたらく", "hataraku", "V5K, VI", "to work; to labor; to function"),
    ("二十日", "はつか", "hatsuka", "N", "twenty days; (the) 20th (day of the month)"),
    ("早い", "はやい", "hayai", "ADJ-I", "early (in the day, etc.); fast, brisk; not yet, (too) early"),
    ("速い", "はやい", "hayai", "ADJ-I", "quick; fast, hasty, brisk"),
    ("辺", "へん", "hen", "N", "area; vicinity; side (of triangle, rectangle, etc.)"),
    ("晴れる", "はれる", "hareru", "V1, VI", "to be sunny; to stop raining; to be cleared"),
    ("春", "はる", "haru", "N-ADV, N-T", "spring; springtime; prime (of one's life)"),
    ("貼る", "はる", "haru", "V5R", "to stick; to paste, to affix"),
    ("橋", "はし", "hashi", "N", "bridge"),
    ("箸", "はし", "hashi", "N", "chopsticks"),
    ("走る", "はしる", "hashiru", "V5R, VI", "to run; to travel; to retreat (from battle)"),
    ("花", "はな", "hana", "N", "flower; blossom, bloom, petal"),
    ("鼻", "はな", "hana", "N", "nose"),
    ("話", "はなし", "hanashi", "N", "talk; story, conversation; discussions"),
    ("話す", "はなす", "hanasu", "V5S, VT", "to speak"),
    ("半分", "はんぶん", "hanbun", "N", "half; halfness, one-half"),
    ("ハンカチ", "", "hankachi", "N", "handkerchief"),
    ("晴れ", "はれ", "hare", "N", "clear weather"),
    ("初めに", "はじめに", "hajime ni", "EXP", "in the beginning; to begin with, first of all"),
    ("初めて", "はじめて", "hajimete", "ADV, N", "for the first time"),
    ("箱", "はこ", "hako", "N", "box"),
    ("履く", "はく", "haku", "V5K, VT", "to put on (lower-body clothing); to put on footwear"),
    ("半", "はん", "han", "N, N-ADV, N-SUF, N-PREF", "half; semi-"),
    ("八", "はち", "hachi", "NUM", "eight"),
    ("葉書", "はがき", "hagaki", "N, ABBR", "postcard; memo, note, card"),
    ("母", "はは", "haha", "N, HUM", "mother"),
    ("はい", "", "hai", "INT, POL", "yes; OK"),
    ("入る", "はいる", "hairu", "V5R", "to enter; to break into; to join, to enroll; to contain"),
    ("灰皿", "はいざら", "haizara", "N", "ashtray"),
    ("始まる", "はじまる", "hajimaru", "V5R, VI", "to begin"),
    ("御飯", "ごはん", "gohan", "N", "cooked rice; meal"),
    ("ご主人", "ごしゅじん", "goshujin", "N, HON", "your husband; her husband"),
    ("午前", "ごぜん", "gozen", "N-ADV, N-T", "morning; a.m."),
    ("グラム", "", "guramu", "N, UK", "gram"),
    ("牛肉", "ぎゅうにく", "gyūniku", "N", "beef"),
    ("牛乳", "ぎゅうにゅう", "gyūnyū", "N", "(cow's) milk"),
    ("歯", "は", "ha", "N", "tooth"),
    ("元気", "げんき", "genki", "ADJ-NA, N", "health; robustness, vigor, vitality, spirit"),
    ("月曜日", "げつようび", "getsuyōbi", "N-ADV, N-T", "Monday"),
    ("銀行", "ぎんこう", "ginkō", "N", "bank"),
    ("ギター", "", "gitā", "N", "guitar"),
    ("五", "ご", "go", "NUM", "five"),
    ("午後", "ごご", "gogo", "N-ADV, N-T", "afternoon; p.m."),
    ("二日", "ふつか", "futsuka", "N", "two days; (the) second (day of the month)"),
    ("冬", "ふゆ", "fuyu", "N-ADV, N-T", "winter"),
    ("外国", "がいこく", "gaikoku", "N", "foreign country; overseas"),
    ("外国人", "がいこくじん", "gaikokujin", "N", "foreigner"),
    ("学校", "がっこう", "gakkō", "N", "school"),
    ("学生", "がくせい", "gakusei", "N", "student (esp. a university student)"),
    ("玄関", "げんかん", "genkan", "N", "entry hall; entranceway"),
    ]),
    ("Ch 04: かぶる–じてんしゃ", [
    ("被る", "かぶる", "kaburu", "V5R, VT", "to wear (on the head)"),
    ("角", "かど", "kado", "N", "(a) corner (of a desk, pavement, etc.); edge"),
    ("帰る", "かえる", "kaeru", "V5R, VI", "to go back; to return (home); to leave"),
    ("返す", "かえす", "kaesu", "V5S, VT", "to return (something); to restore; to turn over"),
    ("鍵", "かぎ", "kagi", "N", "key; lock"),
    ("階段", "かいだん", "kaidan", "N", "stairs; stairway, staircase"),
    ("丈夫", "じょうぶ", "jōbu", "ADJ-NA", "strong; healthy, robust, solid, durable"),
    ("上手", "じょうず", "jōzu", "ADJ-NA, N", "skillful; skill, dexterity"),
    ("十", "じゅう／とお", "jū, tō", "NUM", "ten"),
    ("授業", "じゅぎょう", "jugyō", "N, VS", "lesson; class work"),
    ("鞄", "かばん", "kaban", "N", "bag; satchel, briefcase"),
    ("花瓶", "かびん", "kabin", "N", "a (flower) vase"),
    ("じゃ", "", "ja", "CONJ, INT", "well then...; then, so", "See also: じゃあ (jā) — extended form"),
    ("じゃあ", "", "jā", "CONJ, INT", "well then...; then, so", "See also: じゃ (ja) — short form"),
    ("字引", "じびき", "jibiki", "N", "dictionary"),
    ("自分", "じぶん", "jibun", "N", "oneself; myself, yourself, himself, herself; I, me"),
    ("自動車", "じどうしゃ", "jidōsha", "N", "automobile"),
    ("時間", "じかん", "jikan", "N-ADV, N", "time; hours"),
    ("辞書", "じしょ", "jisho", "N", "dictionary; lexicon"),
    ("自転車", "じてんしゃ", "jitensha", "N", "bicycle"),
    ("痛い", "いたい", "itai", "ADJ-I", "painful; sore"),
    ("いつ", "", "itsu", "ADV-NA, N, UK", "when; how soon"),
    ("五日", "いつか", "itsuka", "N", "five days; fifth (day of the month)"),
    ("いつも", "", "itsumo", "ADV, N, UK", "always; usually, every time; never (with neg. verb)"),
    ("五つ", "いつつ", "itsutsu", "N", "five"),
    ("言う", "いう", "iu", "V5U, VI", "to say; to call (i.e. to give a name)"),
    ("嫌", "いや", "iya", "ADJ-NA, N", "unpleasant; disagreeable, detestable, reluctant"),
    ("居る", "いる", "iru", "V1, VI, UK", "to be (of animate objects); to have; to stay"),
    ("要る", "いる", "iru", "V5R, VI", "to need"),
    ("医者", "いしゃ", "isha", "N", "(medical) doctor; physician, surgeon"),
    ("忙しい", "いそがしい", "isogashii", "ADJ-I", "busy; hectic, occupied, engaged"),
    ("一緒", "いっしょ", "issho", "ADV, N", "together; meeting, company"),
    ("椅子", "いす", "isu", "N", "chair; stool; post, office, position"),
    ("意味", "いみ", "imi", "N, VS", "meaning; significance"),
    ("妹", "いもうと", "imōto", "N, HUM", "younger sister"),
    ("犬", "いぬ", "inu", "N", "dog"),
    ("入れる", "いれる", "ireru", "V1, VT", "to put in; to set; to admit, to employ"),
    ("入口", "いりぐち", "iriguchi", "N, ADJ-NO", "entrance; entry, gate"),
    ("色", "いろ", "iro", "N", "color"),
    ("いろいろ", "", "iroiro", "N, ADJ-NA, ADV", "various"),
    ("良い", "いい／よい", "ii/yoi", "ADJ-I, UK", "good; excellent, fine, nice, pleasant"),
    ("いいえ", "", "iie", "INT, UK", "no; nay, well"),
    ("池", "いけ", "ike", "N", "pond"),
    ("行く", "いく", "iku", "V1, VI", "to go; to leave (for); to advance; to continue"),
    ("いくつ", "", "ikutsu", "ADV, UK", "how many?; how old?"),
    ("今", "いま", "ima", "N-ADV, N", "now; the present time, immediately"),
    ("百", "ひゃく", "hyaku", "NUM", "hundred"),
    ("一", "いち", "ichi", "N, NUM", "one"),
    ("一番", "いちばん", "ichiban", "N-ADV", "best; first, number one"),
    ("一日", "いちにち", "ichinichi", "N", "one day; the first of the month"),
    ("家", "いえ", "ie", "N", "house; residence; household; lineage"),
    ("本", "ほん", "hon", "N", "book; volume"),
    ("本棚", "ほんだな", "hondana", "N", "bookshelves"),
    ("本当", "ほんとう", "hontō", "ADJ-NA, N", "truth; reality"),
    ("本当に", "ほんとうに", "hontō ni", "ADV", "really; truly"),
    ("欲しい", "ほしい", "hoshii", "ADJ-I", "wanted; wished for, in need of, desired"),
    ("細い", "ほそい", "hosoi", "ADJ-I", "thin; slender, fine"),
    ("ホテル", "", "hoteru", "N", "hotel"),
    ("一人", "ひとり", "hitori", "N", "one person"),
    ("一つ", "ひとつ", "hitotsu", "N", "one; for one thing"),
    ("一月", "ひとつき", "hitotsuki", "N", "one month"),
    ("ほう", "", "hō", "ADV, PRT", "one side (of a comparison)"),
    ("ほか", "", "hoka", "ADJ-NO, N", "other (esp. places and things); the rest"),
    ]),
    ("Ch 05: こうちゃ–こんな", [
    ("紅茶", "こうちゃ", "kōcha", "N", "black tea"),
    ("こちら", "", "kochira", "N, UK", "this way; this direction; here; I, me; this person", "See also: こっち (kocchi) — casual form"),
    ("こっち", "", "kocchi", "N, UK", "this way; this direction; here; I, me; this person", "See also: こちら (kochira) — polite form"),
    ("子供", "こども", "kodomo", "N", "child; children"),
    ("公園", "こうえん", "kōen", "N", "(public) park"),
    ("コーヒー", "", "kōhii", "N, ADJ-NO", "coffee"),
    ("ここ", "", "koko", "N", "here; this place"),
    ("喫茶店", "きっさてん", "kissaten", "N", "coffee lounge; coffee shop, cafe"),
    ("北", "きた", "kita", "N", "north"),
    ("汚い", "きたない", "kitanai", "ADJ-I", "dirty; unclean, filthy"),
    ("切手", "きって", "kitte", "N", "(postage) stamp"),
    ("交番", "こうばん", "kōban", "N, VS", "police box"),
    ("声", "こえ", "koe", "N", "voice"),
    ("嫌い", "きらい", "kirai", "ADJ-NA, N", "hate; dislike; suspicion, tendency"),
    ("きれい", "", "kirei", "ADJ-NA, UK", "pretty; beautiful, fair; clean, tidy; completely"),
    ("キロ", "キログラム", "kiro, kiroguramu", "N", "kilogram"),
    ("キロメートル", "", "kiromētoru", "N", "kilometer"),
    ("切る", "きる", "kiru", "V5R, VT", "to cut (through); to sever; to turn off"),
    ("着る", "きる", "kiru", "V1", "to put on (from the shoulders down); to wear"),
    ("黄色", "きいろ", "kiiro", "ADJ-NA, N", "yellow; amber"),
    ("黄色い", "きいろい", "kiiroi", "ADJ-I", "yellow"),
    ("聞く", "きく", "kiku", "V5K, VT", "to hear; to listen; to ask; to enquire"),
    ("昨日", "きのう", "kinō", "N-ADV, N-T", "yesterday"),
    ("金曜日", "きんようび", "kinyōbi", "N-ADV, N-T", "Friday"),
    ("切符", "きっぷ", "kippu", "N", "ticket"),
    ("結構", "けっこう", "kekkō", "ADJ-NA, N-ADV", "splendid; nice; I'm fine (no thank you); tolerable"),
    ("結婚", "けっこん", "kekkon", "N, ADJ-NO, VS", "marriage"),
    ("今朝", "けさ", "kesa", "N-T", "this morning"),
    ("消す", "けす", "kesu", "V5S, VT", "to erase; to delete; to turn off power; to extinguish"),
    ("木", "き", "ki", "N", "tree; wood, timber"),
    ("消える", "きえる", "kieru", "V1, VI", "to disappear; to go out, to vanish"),
    ("可愛い", "かわいい", "kawaii", "ADJ-I", "cute; adorable, lovely, pretty; dear, darling"),
    ("火曜日", "かようび", "kayōbi", "N-ADV, N-T", "Tuesday"),
    ("風", "かぜ", "kaze", "N", "wind; breeze"),
    ("風邪", "かぜ", "kaze", "N", "cold (illness); common cold"),
    ("家族", "かぞく", "kazoku", "N", "family; members of a family"),
    ("警官", "けいかん", "keikan", "N, ADJ-NO", "policeman"),
    ("〜方", "〜かた", "~kata", "N-SUF", "method of; manner of, way of"),
    ("方", "かた", "kata", "N", "direction; way; person, lady, gentleman"),
    ("家庭", "かてい", "katei", "N, ADJ-NO", "household; home"),
    ("買う", "かう", "kau", "V5U, VT", "to buy"),
    ("川", "かわ", "kawa", "N", "river; stream"),
    ("カレー", "", "karē", "N", "curry"),
    ("カレンダー", "", "karendā", "N", "calendar"),
    ("借りる", "かりる", "kariru", "V1, VT", "to borrow; to have a loan; to rent, to hire"),
    ("軽い", "かるい", "karui", "ADJ-I", "light (i.e. not heavy); feeling light; nimble"),
    ("傘", "かさ", "kasa", "N", "umbrella; parasol"),
    ("貸す", "かす", "kasu", "V5S, VT", "to lend; to loan; to rent out, to hire out"),
    ("紙", "かみ", "kami", "N", "paper"),
    ("漢字", "かんじ", "kanji", "N", "kanji"),
    ("顔", "かお", "kao", "N", "(person's) face"),
    ("カップ", "", "kappu", "N", "cup"),
    ("体", "からだ", "karada", "N, ADJ-NO", "body; health"),
    ("辛い", "からい", "karai", "ADJ-I", "spicy; hot; tough; salty"),
    ("買い物", "かいもの", "kaimono", "N", "shopping"),
    ("会社", "かいしゃ", "kaisha", "N", "company; corporation"),
    ("かかる", "", "kakaru", "V5R, VI, UK", "to take (time or money); to hang"),
    ("掛ける", "かける", "kakeru", "V1, VI", "to make (a call)"),
    ("書く", "かく", "kaku", "V5K, VT", "to write"),
    ("カメラ", "", "kamera", "N", "camera"),
    ]),
    ("Ch 06: め–くらす", [
    ("目", "め", "me", "N", "eye; eyeball; eyesight, sight, vision"),
    ("眼鏡", "めがね", "megane", "N", "glasses; spectacles"),
    ("メートル", "", "mētoru", "N", "meter"),
    ("道", "みち", "michi", "N", "street; road, way, path, route, lane"),
    ("緑", "みどり", "midori", "N", "green"),
    ("磨く", "みがく", "migaku", "V5K, VT", "to brush (teeth); to polish, to shine; to improve"),
    ("右", "みぎ", "migi", "N", "right; right-hand side"),
    ("丸い", "まるい", "marui", "ADJ-I", "round; circular, spherical"),
    ("真っすぐ", "まっすぐ", "massugu", "ADJ-NA, ADV, N", "straight (ahead); upright, erect; straightforward"),
    ("また", "", "mata", "ADV, CONJ, UK", "again; and, also, still (doing something)"),
    ("待つ", "まつ", "matsu", "V5T, VT", "to wait; to look forward to"),
    ("まずい", "", "mazui", "ADJ-I, UK", "unpleasant (taste, appearance, situation); unappetizing"),
    ("毎晩", "まいばん", "maiban", "N-ADV, N-T", "every night"),
    ("毎月", "まいげつ／まいつき", "maigetsu/maitsuki", "N-ADV, N-T", "every month"),
    ("毎年", "まいねん／まいとし", "mainen/maitoshi", "N-ADV, N-T", "every year"),
    ("毎日", "まいにち", "mainichi", "N-ADV, N-T", "every day"),
    ("毎週", "まいしゅう", "maishū", "N-ADV, N-T", "every week"),
    ("万", "まん", "man", "NUM", "ten thousand"),
    ("万年筆", "まんねんひつ", "mannenhitsu", "N", "fountain pen"),
    ("町", "まち", "machi", "N", "town; block, neighborhood; street, road"),
    ("まだ", "", "mada", "ADJ-NA, ADV, UK", "as yet; still; not yet (with negative verb)"),
    ("窓", "まど", "mado", "N", "window"),
    ("前", "まえ", "mae", "N-ADV, N-T, SUF", "before; ago; in front (of)"),
    ("曲がる", "まがる", "magaru", "V5R, VI", "to bend; to warp, to twist; to turn; to be crooked"),
    ("毎朝", "まいあさ", "maiasa", "N-ADV, N-T", "every morning"),
    ("靴下", "くつした", "kutsushita", "N", "socks; stockings"),
    ("今日", "きょう", "kyō", "N-T", "today; this day"),
    ("兄弟", "きょうだい", "kyōdai", "N", "siblings; brothers and sisters"),
    ("去年", "きょねん", "kyonen", "N-ADV, N-T", "last year"),
    ("教室", "きょうしつ", "kyōshitsu", "N", "classroom"),
    ("九", "きゅう／く", "kyū/ku", "NUM", "nine"),
    ("マッチ", "", "macchi", "N", "match (contest); match (to light fire with)"),
    ("黒", "くろ", "kuro", "N", "black; dark"),
    ("黒い", "くろい", "kuroi", "ADJ-I", "black; dark; illicit, wicked"),
    ("来る", "くる", "kuru", "VK, VI", "to come; to approach, to arrive; to come back"),
    ("車", "くるま", "kuruma", "N", "car; automobile, vehicle; wheel"),
    ("薬", "くすり", "kusuri", "N", "medicine; pharmaceuticals, drugs"),
    ("靴", "くつ", "kutsu", "N", "shoes; footwear"),
    ("曇り", "くもり", "kumori", "N", "cloudy weather; cloudiness, shadow"),
    ("曇る", "くもる", "kumoru", "V5R, VI", "to become cloudy; to become dim; to fog up"),
    ("国", "くに", "kuni", "N", "country; (the) state; region; home (i.e. hometown)"),
    ("暗い", "くらい", "kurai", "ADJ-I, UK", "gloomy; dark; dull; depressed"),
    ("クラス", "", "kurasu", "N", "class"),
    ("答える", "こたえる", "kotaeru", "V1, VI", "to answer; to reply"),
    ("コート", "", "kōto", "N", "coat; court (i.e. tennis, basketball)"),
    ("言葉", "ことば", "kotoba", "N", "language; dialect; word(s), expression"),
    ("今年", "ことし", "kotoshi", "N-ADV, N-T", "this year"),
    ("口", "くち", "kuchi", "N", "mouth; opening, hole, gap"),
    ("果物", "くだもの", "kudamono", "N", "fruit"),
    ("下さい", "ください", "kudasai", "UK, HON", "please (give me); please (do for me)"),
    ("この", "", "kono", "ADJ-PN, UK", "this"),
    ("今週", "こんしゅう", "konshū", "N-ADV, N-T", "this week"),
    ("コピー", "", "kopii", "N, VS", "copy; photocopy"),
    ("コップ", "", "koppu", "N", "a glass; tumbler"),
    ("これ", "", "kore", "N, UK", "this"),
    ("交差点", "こうさてん", "kōsaten", "N", "intersection; crossing"),
    ("九日", "ここのか", "kokonoka", "N", "nine days; ninth (day of the month)"),
    ("九つ", "ここのつ", "kokonotsu", "N", "nine"),
    ("困る", "こまる", "komaru", "V5R, VI", "to be worried; to be bothered, to be troubled"),
    ("今晩", "こんばん", "konban", "N-ADV, N-T", "this evening; tonight"),
    ("今月", "こんげつ", "kongetsu", "N-ADV, N-T", "this month"),
    ("こんな", "", "konna", "ADJ-PN", "such; like this"),
    ]),
    ("Ch 07: ないふ–おちゃ", [
    ("ナイフ", "", "naifu", "N", "knife"),
    ("伯母さん", "おばさん", "obasan", "N, HON", "aunt; middle-aged woman, ma'am"),
    ("お祖母さん", "おばあさん", "obāsan", "N", "grandmother; old woman, elderly woman"),
    ("お弁当", "おべんとう", "obentō", "N", "(Japanese) box lunch"),
    ("覚える", "おぼえる", "oboeru", "V1, VT", "to remember; to recollect, to memorize; to feel"),
    ("お茶", "おちゃ", "ocha", "N", "tea (usually green); tea ceremony"),
    ("飲む", "のむ", "nomu", "V5M, VT", "to drink; to swallow; to take (medicine)"),
    ("乗る", "のる", "noru", "V5R, VI", "to get on; to ride in; to spread; to share in"),
    ("ノート", "", "nōto", "N, VS", "notebook; exercise book; note"),
    ("脱ぐ", "ぬぐ", "nugu", "V5G, VT", "to take off (clothes, shoes, etc.); to undress"),
    ("温い", "ぬるい", "nurui", "ADJ-I, UK", "lukewarm; tepid"),
    ("ニュース", "", "nyūsu", "N", "news"),
    ("賑やか", "にぎやか", "nigiyaka", "ADJ-NA", "bustling; busy, crowded; lively"),
    ("肉", "にく", "niku", "N", "meat; flesh"),
    ("荷物", "にもつ", "nimotsu", "N", "luggage; baggage"),
    ("西", "にし", "nishi", "N", "west"),
    ("庭", "にわ", "niwa", "N", "garden"),
    ("登る", "のぼる", "noboru", "V5R, VI", "to climb; to go up; to ascend"),
    ("飲み物", "のみもの", "nomimono", "N", "(a) drink; a beverage"),
    ("夏休み", "なつやすみ", "natsuyasumi", "N", "summer vacation; summer holiday"),
    ("なぜ", "", "naze", "ADV, UK", "why; how"),
    ("猫", "ねこ", "neko", "N", "cat"),
    ("ネクタイ", "", "nekutai", "N", "tie; necktie"),
    ("寝る", "ねる", "neru", "V1, VI", "to lie down; to go to bed; to sleep"),
    ("二", "に", "ni", "NUM", "two"),
    ("日曜日", "にちようび", "nichiyōbi", "N-ADV, N-T", "Sunday"),
    ("七つ", "ななつ", "nanatsu", "N", "seven"),
    ("七日", "なのか", "nanoka", "N-ADV", "seven days; (the) seventh (day of the month)"),
    ("並べる", "ならべる", "naraberu", "V1, VT", "to line up; to set up"),
    ("並ぶ", "ならぶ", "narabu", "V5B, VI", "to line up; to stand in a line; to rival"),
    ("習う", "ならう", "narau", "V5U, VT", "to learn"),
    ("なる", "", "naru", "V5R, VI, UK", "to become; to get, to grow, to be"),
    ("夏", "なつ", "natsu", "N-ADV, N-T", "summer"),
    ("中", "なか", "naka", "N", "middle; center; in; among, within; during"),
    ("泣く", "なく", "naku", "V5K", "to cry; to weep, to sob, to howl"),
    ("鳴く", "なく", "naku (animal)", "V5K", "to bark; to make sound (animal); to sing (bird)"),
    ("無くす", "なくす", "nakusu", "V5S, VT", "to lose something"),
    ("名前", "なまえ", "namae", "N", "name; full name; given name"),
    ("何", "なん／なに", "nan/nani", "INT, PN", "what"),
    ("向こう", "むこう", "mukō", "N", "over there; that way, far away; opposite direction"),
    ("村", "むら", "mura", "N", "village"),
    ("六つ", "むっつ", "muttsu", "NUM", "six"),
    ("難しい", "むずかしい", "muzukashii", "ADJ-I", "difficult; hard, troublesome, complicated"),
    ("等", "など", "nado", "N, PRT, UK", "et cetera; etc, and the like"),
    ("長い", "ながい", "nagai", "ADJ-I", "long (distance); long (time), lengthy"),
    ("木曜日", "もくようび", "mokuyōbi", "N-ADV, N-T", "Thursday"),
    ("門", "もん", "mon", "N, N-SUF", "gate"),
    ("問題", "もんだい", "mondai", "N", "problem; question"),
    ("物", "もの", "mono", "N", "thing; object"),
    ("持つ", "もつ", "motsu", "V5T", "to hold; to carry; to possess"),
    ("もっと", "", "motto", "ADV", "more; even more, longer, further"),
    ("六日", "むいか", "muika", "N", "(the) sixth day (of the month); six days"),
    ("見せる", "みせる", "miseru", "V1, VT", "to show; to display"),
    ("三つ", "みっつ", "mittsu", "N", "three"),
    ("水", "みず", "mizu", "N", "water (cold, fresh)"),
    ("もう", "", "mō", "ADV, INT, UK", "already; anymore; soon; more, further"),
    ("もう一度", "もういちど", "mō ichido", "EXP", "again; once more"),
    ("もちろん", "", "mochiron", "ADV, UK", "of course; certainly, naturally"),
    ("短い", "みじかい", "mijikai", "ADJ-I", "short"),
    ("三日", "みっか", "mikka", "N", "three days; (the) third (day of the month)"),
    ("耳", "みみ", "mimi", "N", "ear; hearing; edge, crust"),
    ("皆", "みな／みんな", "mina, minna", "ADV, N", "everyone; all, everybody; everything"),
    ("南", "みなみ", "minami", "N", "south"),
    ("見る", "みる", "miru", "V1, VT", "to see; to watch; to look over"),
    ("店", "みせ", "mise", "N", "shop; store, establishment"),
    ]),
    ("Ch 08: れんしゅう–おかね", [
    ("練習", "れんしゅう", "renshū", "N, VS", "practice"),
    ("レストラン", "", "resutoran", "N", "restaurant"),
    ("りんご", "", "ringo", "N", "apple"),
    ("立派", "りっぱ", "rippa", "ADJ-NA, N", "splendid; handsome, prominent, legitimate"),
    ("廊下", "ろうか", "rōka", "N", "corridor; hallway, passageway"),
    ("六", "ろく", "roku", "NUM", "six"),
    ("旅行", "りょこう", "ryokō", "N, VS, ADJ-NO", "travel; trip"),
    ("来年", "らいねん", "rainen", "N-ADV, N-T", "next year"),
    ("来週", "らいしゅう", "raishū", "N-ADV, N-T", "next week"),
    ("ラジカセ", "", "rajikase", "N", "radio cassette player"),
    ("ラジオ", "", "rajio", "N", "radio"),
    ("零", "れい", "rei", "N, ADJ-NO", "zero; nought"),
    ("冷蔵庫", "れいぞうこ", "reizōko", "N", "refrigerator"),
    ("レコード", "", "rekōdo", "N", "record"),
    ("ページ", "", "pēji", "N", "page"),
    ("ペン", "", "pen", "N", "pen"),
    ("ペット", "", "petto", "N", "pet"),
    ("ポケット", "", "poketto", "N", "pocket"),
    ("ポスト", "", "posuto", "N, VS", "post; position; postbox"),
    ("プール", "", "pūru", "N", "swimming pool"),
    ("来月", "らいげつ", "raigetsu", "N-ADV, N-T", "next month"),
    ("一昨年", "おととし", "ototoshi", "N-ADV, N-T", "year before last; two years ago"),
    ("終わる", "おわる", "owaru", "V5R, VI", "to finish; to end, to close"),
    ("泳ぐ", "およぐ", "oyogu", "V5G, VI", "to swim"),
    ("大勢", "おおぜい", "ōzei", "N, ADJ-NO", "crowd (of people); many, great number of people"),
    ("パン", "", "pan", "N", "bread"),
    ("パーティー", "", "pātii", "N", "party"),
    ("お手洗い", "おてあらい", "otearai", "N", "bathroom; toilet, restroom, lavatory"),
    ("男", "おとこ", "otoko", "N", "man"),
    ("男の子", "おとこのこ", "otoko no ko", "N", "boy; male child, baby boy"),
    ("大人", "おとな", "otona", "N", "adult"),
    ("お父さん", "おとうさん", "otōsan", "N, HON", "father"),
    ("弟", "おとうと", "otōto", "N, HUM", "younger brother"),
    ("一昨日", "おととい", "ototoi", "N-ADV, N-T", "day before yesterday"),
    ("降りる", "おりる", "oriru", "V1, VI", "to descend; to go down; to get off, to dismount"),
    ("お酒", "おさけ", "osake", "N", "alcohol; sake"),
    ("お皿", "おさら", "osara", "N", "plate; dish"),
    ("教える", "おしえる", "oshieru", "V1, VT", "to teach; to inform, to tell, to instruct"),
    ("遅い", "おそい", "osoi", "ADJ-I", "slow; late; too late"),
    ("押す", "おす", "osu", "V5S, VT", "to push; to press (down); to stamp"),
    ("お腹", "おなか", "onaka", "N", "stomach"),
    ("お姉さん", "おねえさん", "onēsan", "N, HON", "older sister; young lady; miss"),
    ("音楽", "おんがく", "ongaku", "N", "music; musical movement"),
    ("お兄さん", "おにいさん", "oniisan", "N, HON", "older brother; young man, buddy"),
    ("女", "おんな", "onna", "N", "woman"),
    ("女の子", "おんなのこ", "onna no ko", "N", "girl"),
    ("置く", "おく", "oku", "V5K", "to put; to leave (behind); to do sth in advance"),
    ("奥さん", "おくさん", "okusan", "N, HON", "(your) wife; wife, married lady, madam"),
    ("お巡りさん", "おまわりさん", "omawari-san", "N", "(friendly term for a) policeman"),
    ("重い", "おもい", "omoi", "ADJ-I", "heavy; massive; serious, oppressed"),
    ("面白い", "おもしろい", "omoshiroi", "ADJ-I", "interesting; amusing"),
    ("同じ", "おなじ", "onaji", "ADJ-F, N", "same; identical, common, changeless"),
    ("お母さん", "おかあさん", "okāsan", "N, HON", "mother"),
    ("お菓子", "おかし", "okashi", "N", "sweets; confections, candy"),
    ("大きい", "おおきい", "ōkii", "ADJ-I", "big; large, great"),
    ("大きな", "おおきな", "ōkina", "ADJ-F", "big; large, great"),
    ("起きる", "おきる", "okiru", "V1, VI", "to get up; to rise; to wake up; to occur"),
    ("お風呂", "おふろ", "ofuro", "N", "bath"),
    ("多い", "おおい", "ōi", "ADJ-I", "many; numerous"),
    ("おいしい", "", "oishii", "ADJ-I, UK", "delicious; tasty"),
    ("お祖父さん", "おじいさん", "ojiisan", "N, HON", "grandfather; old man, elderly man"),
    ("おじさん", "", "ojisan", "N, HON, UK", "uncle; older man, middle-aged man"),
    ("お金", "おかね", "okane", "N", "money"),
    ]),
    ("Ch 09: それから–さかな", [
    ("それから", "", "sore kara", "EXP, UK", "after that; and then"),
    ("そして", "", "soshite", "CONJ, UK", "and then; and, thus, and now"),
    ("そうして", "", "sōshite", "CONJ, UK", "and; like that"),
    ("外", "そと", "soto", "N", "outside; exterior; open air"),
    ("すぐに", "", "sugu ni", "ADV, UK", "instantly; immediately"),
    ("水曜日", "すいようび", "suiyōbi", "N-ADV, N-T", "Wednesday"),
    ("スカート", "", "sukāto", "N", "skirt"),
    ("その", "", "sono", "ADJ-PN, UK", "that; the; um..., er..."),
    ("空", "そら", "sora", "N", "sky; the heavens, air"),
    ("それ", "", "sore", "N, UK", "that; it; that time, then"),
    ("それでは", "", "sore de wa", "EXP, UK", "in that situation; well then..."),
    ("宿題", "しゅくだい", "shukudai", "N", "homework"),
    ("側", "そば", "soba", "N", "near; beside, vicinity"),
    ("そちら", "", "sochira", "N, UK", "that way (by you); there; you, your family", "See also: そっち (socchi) — casual form"),
    ("そっち", "", "socchi", "N, UK", "that way (by you); there; you, your family", "See also: そちら (sochira) — polite form"),
    ("掃除", "そうじ", "sōji", "N, VS", "cleaning; sweeping"),
    ("そこ", "", "soko", "N, UK", "there; then"),
    ("白い", "しろい", "shiroi", "ADJ-I", "white"),
    ("知る", "しる", "shiru", "V5R, VT", "to know; to understand, to be acquainted with"),
    ("下", "した", "shita", "N", "below; under; bottom; underneath"),
    ("質問", "しつもん", "shitsumon", "N, VS", "question; inquiry, enquiry"),
    ("静か", "しずか", "shizuka", "ADJ-NA", "quiet; peaceful"),
    ("食堂", "しょくどう", "shokudō", "N", "dining hall; cafeteria; restaurant"),
    ("醤油", "しょうゆ", "shōyu", "N", "soy sauce"),
    ("閉まる", "しまる", "shimaru", "V5R, VI", "to close; to be closed; to be locked"),
    ("締める", "しめる", "shimeru", "V1, VT", "to tighten; to tie; to total; to be strict with"),
    ("閉める", "しめる", "shimeru", "V1, VT", "to close; to shut, to shut down"),
    ("新聞", "しんぶん", "shinbun", "N", "newspaper"),
    ("死ぬ", "しぬ", "shinu", "V5N, VI", "to die"),
    ("塩", "しお", "shio", "N", "salt; common salt, table salt"),
    ("白", "しろ", "shiro", "N", "white"),
    ("シャツ", "", "shatsu", "N", "shirt; singlet"),
    ("シャワー", "", "shawā", "N", "shower"),
    ("四", "し／よん", "shi/yon", "NUM", "four"),
    ("七", "しち／なな", "shichi, nana", "NUM", "seven"),
    ("仕事", "しごと", "shigoto", "N, VS, ADJ-NO", "job; business, occupation, employment, task"),
    ("しかし", "", "shikashi", "CONJ, UK", "however; but"),
    ("千", "せん", "sen", "NUM", "thousand; 1000"),
    ("先月", "せんげつ", "sengetsu", "N-ADV, N-T", "last month"),
    ("先生", "せんせい", "sensei", "N", "teacher; doctor; honorific title"),
    ("先週", "せんしゅう", "senshū", "N-ADV, N-T", "last week; the week before"),
    ("洗濯", "せんたく", "sentaku", "N, VS", "washing; laundry"),
    ("セーター", "", "sētā", "N", "sweater, jumper"),
    ("写真", "しゃしん", "shashin", "N", "photograph; picture"),
    ("差す", "さす", "sasu", "V5S, VI", "to hold up (an umbrella); to put up, to raise"),
    ("砂糖", "さとう", "satō", "N", "sugar"),
    ("背", "せ", "se", "N", "height; stature; back"),
    ("背広", "せびろ", "sebiro", "N", "business suit"),
    ("生徒", "せいと", "seito", "N", "pupil"),
    ("せっけん", "", "sekken", "N, VS", "soap"),
    ("狭い", "せまい", "semai", "ADJ-I", "narrow; confined, small"),
    ("先", "さき", "saki", "N, ADJ-NO", "previous; prior, some time ago, preceding"),
    ("咲く", "さく", "saku", "V5K, VI", "to bloom"),
    ("作文", "さくぶん", "sakubun", "N, VS", "writing; composition"),
    ("寒い", "さむい", "samui", "ADJ-I", "cold"),
    ("三", "さん", "san", "NUM", "three"),
    ("散歩する", "さんぽする", "sanpo suru", "N, VS", "to stroll; to go for a walk"),
    ("再来年", "さらいねん", "sarainen", "N-ADV, N-T", "year after next"),
    ("料理", "りょうり", "ryōri", "N, VS", "cuisine; cooking, cookery"),
    ("両親", "りょうしん", "ryōshin", "N", "both parents; parents"),
    ("留学生", "りゅうがくせい", "ryūgakusei", "N", "overseas student; exchange student"),
    ("さあ", "", "sā", "CONJ, INT", "well..."),
    ("財布", "さいふ", "saifu", "N", "wallet; purse, handbag"),
    ("魚", "さかな", "sakana", "N", "fish"),
    ]),
    ("Ch 10: つくる–すりっぱ", [
    ("作る", "つくる", "tsukuru", "V5R, VT", "to make; to produce; to brew (alcohol); to cultivate"),
    ("つまらない", "", "tsumaranai", "ADJ-I, UK", "boring; dull, uninteresting; insignificant"),
    ("冷たい", "つめたい", "tsumetai", "ADJ-I", "cold (to the touch); chilly, icy, freezing"),
    ("勤める", "つとめる", "tsutomeru", "V1, VT", "to work for sb; to serve (in)"),
    ("強い", "つよい", "tsuyoi", "ADJ-I", "powerful; strong; resistant, durable"),
    ("上", "うえ", "ue", "N, ADJ-NO", "above; over; top; surface; before; previous"),
    ("疲れる", "つかれる", "tsukareru", "V1, VI", "to get tired; to tire"),
    ("使う", "つかう", "tsukau", "V5U, VT", "to use; to employ; to make use of"),
    ("点ける", "つける", "tsukeru", "V1, VT, UK", "to turn on; to switch on, to light up"),
    ("着く", "つく", "tsuku", "V5K", "to arrive at; to reach; to sit on"),
    ("机", "つくえ", "tsukue", "N", "desk"),
    ("鳥", "とり", "tori", "N", "bird; bird meat (esp. chicken meat)"),
    ("撮る", "とる", "toru", "V5R, VT", "to take (a photo); to make (a film)"),
    ("取る", "とる", "toru", "V5R, VT", "to take; to pick up; to steal; to have (a meal)"),
    ("年", "とし", "toshi", "N-ADV, N", "year; age"),
    ("図書館", "としょかん", "toshokan", "N", "library"),
    ("とても", "", "totemo", "ADV, UK", "very; exceedingly; (w/neg. form) (not) at all"),
    ("次", "つぎ", "tsugi", "N, ADJ-NO", "next; following, subsequent"),
    ("十日", "とおか", "tōka", "N", "ten days; (the) tenth (of the month)"),
    ("時計", "とけい", "tokei", "N", "watch; clock, timepiece"),
    ("時々", "ときどき", "tokidoki", "ADV, N", "sometimes; at times"),
    ("所", "ところ", "tokoro", "N, SUF", "place; spot, scene, site"),
    ("止まる", "とまる", "tomaru", "V5R, VI", "to stop; to halt; to come to a halt"),
    ("友達", "ともだち", "tomodachi", "N", "friend; companion"),
    ("隣", "となり", "tonari", "N, ADJ-NO", "next to; neighbor"),
    ("テープレコーダー", "", "tēpu rekōdā", "N", "tape recorder"),
    ("テレビ", "", "terebi", "N, ABBR", "television; TV"),
    ("テスト", "", "tesuto", "N", "test"),
    ("戸", "と", "to", "N", "Japanese style door"),
    ("飛ぶ", "とぶ", "tobu", "V5B, VI", "to jump; to leap; to fly, to soar"),
    ("遠い", "とおい", "tōi", "ADJ-I", "far; distant"),
    ("トイレ", "", "toire", "N, ABBR", "toilet; restroom, bathroom"),
    ("建物", "たてもの", "tatemono", "N", "building"),
    ("立つ", "たつ", "tatsu", "V5T, VI", "to stand; to rise, to stand up"),
    ("手", "て", "te", "N", "hand; arm; handle"),
    ("テーブル", "", "tēburu", "N", "table"),
    ("手紙", "てがみ", "tegami", "N", "letter"),
    ("天気", "てんき", "tenki", "N", "weather; fine weather"),
    ("テープ", "", "tēpu", "N", "tape"),
    ("たくさん", "", "takusan", "ADJ-NA, ADV, N, UK", "many; a lot, much"),
    ("タクシー", "", "takushii", "N", "taxi"),
    ("卵", "たまご", "tamago", "N", "(hen) egg(s); spawn, roe"),
    ("誕生日", "たんじょうび", "tanjōbi", "N", "birthday"),
    ("頼む", "たのむ", "tanomu", "V5M", "to ask; to beg; to order, to reserve"),
    ("楽しい", "たのしい", "tanoshii", "ADJ-I", "enjoyable; fun"),
    ("縦", "たて", "tate", "N", "(the) vertical; height; length; longitudinal"),
    ("食べる", "たべる", "taberu", "V1, VT", "to eat"),
    ("たぶん", "", "tabun", "ADV, N", "probably; perhaps"),
    ("大変", "たいへん", "taihen", "ADV", "very; greatly; immense; serious, terrible"),
    ("大切", "たいせつ", "taisetsu", "ADJ-NA, N", "important; valuable, worthy of care"),
    ("大使館", "たいしかん", "taishikan", "N", "embassy"),
    ("たいてい", "", "taitei", "ADJ-NA, ADV, N, UK", "mostly; ordinarily; probably; almost all"),
    ("高い", "たかい", "takai", "ADJ-I", "high; tall; expensive"),
    ("する", "", "suru", "VS-I, UK", "to do; to make (into); to work as"),
    ("ストーブ", "", "sutōbu", "N", "heater"),
    ("吸う", "すう", "suu", "V5U, VT", "to smoke; to inhale; to suck; to absorb"),
    ("座る", "すわる", "suwaru", "V5R, VI", "to sit; to squat; to assume (a position)"),
    ("涼しい", "すずしい", "suzushii", "ADJ-I", "refreshing; cool"),
    ("たばこ", "", "tabako", "N, UK", "tobacco; cigarettes"),
    ("食べ物", "たべもの", "tabemono", "N", "food"),
    ("好き", "すき", "suki", "ADJ-NA, N", "liking; fondness, love"),
    ("少し", "すこし", "sukoshi", "ADV, N", "a bit; a little, small quantity"),
    ("少ない", "すくない", "sukunai", "ADJ-I", "a few; a little, insufficient, seldom"),
    ("住む", "すむ", "sumu", "V5M, VI", "to live (of humans); to reside, to inhabit"),
    ("スポーツ", "", "supōtsu", "N, ADJ-NO", "sport"),
    ("スプーン", "", "supūn", "N", "spoon"),
    ("スリッパ", "", "surippa", "N", "slippers"),
    ]),
    ("Ch 11: ゆき–うた", [
    ("雪", "ゆき", "yuki", "N", "snow"),
    ("ゆっくりと", "", "yukkuri to", "ADV, N", "slowly; at ease, restful"),
    ("有名", "ゆうめい", "yūmei", "ADJ-NA", "famous; well-known"),
    ("雑誌", "ざっし", "zasshi", "N", "magazine; journal, periodical"),
    ("全部", "ぜんぶ", "zenbu", "N-ADV, N-T", "all; entire, whole, altogether"),
    ("ゼロ", "", "zero", "N, ADJ-NO", "zero"),
    ("ズボン", "", "zubon", "N", "trousers; pants"),
    ("夜", "よる", "yoru", "N-ADV, N-T", "evening; night"),
    ("四つ", "よっつ", "yottsu", "NUM", "four"),
    ("弱い", "よわい", "yowai", "ADJ-I", "weak; delicate, unskilled"),
    ("昨夜", "ゆうべ", "yūbe", "N-ADV, N-T", "last night"),
    ("郵便局", "ゆうびんきょく", "yūbinkyoku", "N", "post office"),
    ("夕方", "ゆうがた", "yūgata", "N-ADV, N-T", "evening; dusk"),
    ("夕飯", "ゆうはん", "yūhan", "N", "dinner; evening meal"),
    ("八日", "ようか", "yōka", "N", "eight days; (the) eighth day (of the month)"),
    ("四日", "よっか", "yokka", "N", "four days; (the) fourth day (of the month)"),
    ("横", "よこ", "yoko", "N", "horizontal; width; side; beside"),
    ("よく", "", "yoku", "ADV, UK", "well; skillfully; often, frequently"),
    ("読む", "よむ", "yomu", "V5M, VT", "to read"),
    ("より", "", "yori", "ADV, PRT", "than (used for comparison)"),
    ("野菜", "やさい", "yasai", "N, ADJ-NO", "vegetable"),
    ("易しい", "やさしい", "yasashii", "ADJ-I", "easy; plain, simple"),
    ("安い", "やすい", "yasui", "ADJ-I", "cheap; inexpensive"),
    ("休み", "やすみ", "yasumi", "N", "rest; recess; vacation"),
    ("八つ", "やっつ", "yattsu", "NUM", "eight"),
    ("呼ぶ", "よぶ", "yobu", "V5B, VT", "to call out; to summon; to invite"),
    ("洋服", "ようふく", "yōfuku", "N", "Western-style clothes"),
    ("忘れる", "わすれる", "wasureru", "V1, VT", "to forget; to leave carelessly"),
    ("渡す", "わたす", "watasu", "V5S, VT", "to hand over; to ferry across; to go across"),
    ("私", "わたし", "watashi", "PN, ADJ-NO", "I, myself"),
    ("山", "やま", "yama", "N", "mountain; hill"),
    ("八百屋", "やおや", "yaoya", "N", "greengrocer"),
    ("やる", "", "yaru", "V5R, VT, UK, COL", "to do"),
    ("歌う", "うたう", "utau", "V5U, VT", "to sing"),
    ("美しい", "うつくしい", "utsukushii", "ADJ-I", "beautiful"),
    ("上着", "うわぎ", "uwagi", "N, ADJ-NO", "jacket; coat, tunic, outer garment"),
    ("ワイシャツ", "", "waishatsu", "N, UK, ABBR", "business shirt; shirt, dress shirt"),
    ("若い", "わかい", "wakai", "ADJ-I", "young"),
    ("分かる", "わかる", "wakaru", "V5R, VI", "to be understood; to be comprehended"),
    ("悪い", "わるい", "warui", "ADJ-I", "bad; inferior; evil; unprofitable"),
    ("生まれる", "うまれる", "umareru", "V1, VI", "to be born"),
    ("海", "うみ", "umi", "N", "sea; beach, ocean"),
    ("売る", "うる", "uru", "V5R, VT", "to sell"),
    ("煩い", "うるさい", "urusai", "ADJ-I, UK", "noisy; fussy; annoying, tiresome"),
    ("後ろ", "うしろ", "ushiro", "N", "behind; back, rear"),
    ("薄い", "うすい", "usui", "ADJ-I", "thin; light; watery; weak (taste)"),
    ("歌", "うた", "uta", "N", "song; (classical) Japanese poetry"),
    ]),
]


def make_id(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


SEE_ALSO_HTML = (
    '{{#SeeAlso}}<div class="see-also">{{SeeAlso}}</div>{{/SeeAlso}}'
)

CARD_CSS = """\
.card {
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background: #1a1a2e; color: #eee; padding: 20px;
}
hr { border: none; border-top: 1px solid #333; margin: 16px 0; }
.see-also {
  font-size: 13px; text-align: center; color: #8b5cf6;
  margin-top: 10px; font-style: italic;
}
.reading-box {
  font-size: 18px; text-align: center; color: #888; margin-top: 8px;
}
.reading-toggle {
  font-size: 13px; text-align: center; margin-top: 6px;
}
.reading-toggle a {
  color: #555; text-decoration: none; cursor: pointer;
}
.reading-toggle a:hover { color: #8b5cf6; }
.intro { text-align: left; line-height: 1.7; }
.intro h2 { text-align: center; margin-bottom: 16px; }
.intro ul { padding-left: 20px; }
.intro li { margin-bottom: 6px; }
.intro .key { color: #8b5cf6; font-weight: 600; }
.setting-toggle {
  display: inline-block; padding: 6px 14px; border-radius: 8px;
  background: #2a2a4e; border: 1px solid #444; color: #ccc;
  cursor: pointer; font-size: 14px; margin: 4px;
}
.setting-toggle.active {
  background: #8b5cf6; border-color: #8b5cf6; color: #fff;
}
"""

READING_JS = """\
<script>
(function() {
  var el = document.getElementById('reading');
  var toggle = document.getElementById('reading-tap');
  var show;
  try { show = localStorage.getItem('jlpt_show_reading') !== 'false'; }
  catch(e) { show = true; }
  if (show) { el.style.display = ''; toggle.textContent = 'tap to hide reading'; }
  else { el.style.display = 'none'; toggle.textContent = 'tap to show reading'; }
  toggle.onclick = function(e) {
    e.preventDefault();
    show = !show;
    try { localStorage.setItem('jlpt_show_reading', show); } catch(e) {}
    if (show) { el.style.display = ''; toggle.textContent = 'tap to hide reading'; }
    else { el.style.display = 'none'; toggle.textContent = 'tap to show reading'; }
  };
})();
</script>"""

MODEL = genanki.Model(
    make_id("jlpt_n5_vocab_model_v5"),
    "JLPT N5 Vocabulary",
    fields=[
        {"name": "Kanji"},
        {"name": "Reading"},
        {"name": "Romaji"},
        {"name": "PartOfSpeech"},
        {"name": "Meaning"},
        {"name": "SeeAlso"},
    ],
    templates=[
        {
            "name": "Recognize",
            "qfmt": (
                '<div style="font-size:48px;text-align:center;font-family:serif;">'
                "{{Kanji}}</div>"
                '<div id="reading" class="reading-box">{{Reading}}</div>'
                '<div class="reading-toggle">'
                '<a id="reading-tap">tap to show reading</a></div>'
            ) + READING_JS,
            "afmt": (
                '<div style="font-size:48px;text-align:center;font-family:serif;">'
                "{{Kanji}}</div>"
                '<div style="font-size:18px;text-align:center;color:#888;margin-top:8px;">'
                "{{Reading}}</div>"
                "<hr>"
                '<div style="font-size:14px;text-align:center;color:#aaa;">'
                "{{Romaji}} — {{PartOfSpeech}}</div>"
                '<div style="font-size:22px;text-align:center;margin-top:12px;">'
                "{{Meaning}}</div>"
            ) + SEE_ALSO_HTML,
        },
        {
            "name": "Recall",
            "qfmt": (
                '<div style="font-size:22px;text-align:center;">{{Meaning}}</div>'
                '<div style="font-size:14px;text-align:center;color:#aaa;margin-top:4px;">'
                "{{PartOfSpeech}}</div>"
            ),
            "afmt": (
                "{{FrontSide}}<hr>"
                '<div style="font-size:48px;text-align:center;font-family:serif;">'
                "{{Kanji}}</div>"
                '<div style="font-size:18px;text-align:center;color:#888;">'
                "{{Reading}}</div>"
                '<div style="font-size:14px;text-align:center;color:#aaa;">'
                "{{Romaji}}</div>"
            ) + SEE_ALSO_HTML,
        },
    ],
    css=CARD_CSS,
)

INTRO_MODEL = genanki.Model(
    make_id("jlpt_n5_intro_model_v1"),
    "JLPT N5 — Intro",
    fields=[{"name": "Content"}],
    templates=[{
        "name": "Intro",
        "qfmt": '{{Content}}',
        "afmt": '{{Content}}',
    }],
    css=CARD_CSS,
)

INTRO_HTML = """\
<div class="intro">
<h2>JLPT N5 Vocabulary Deck</h2>
<p>676 words across 11 chapters. Each word has two card types:</p>
<ul>
  <li><span class="key">Recognize</span> — see the kanji, recall the meaning</li>
  <li><span class="key">Recall</span> — see the English, recall the Japanese</li>
</ul>
<h3>Reading / Furigana Setting</h3>
<p>On <span class="key">Recognize</span> cards you can choose whether the \
reading (furigana) is shown or hidden by default. Pick your preference below \
— it will be remembered across sessions.</p>
<div style="text-align:center;margin:16px 0;">
  <span id="btn-show" class="setting-toggle" onclick="setPref(true)">Show reading</span>
  <span id="btn-hide" class="setting-toggle" onclick="setPref(false)">Hide reading</span>
</div>
<p style="text-align:center;font-size:13px;color:#888;" id="pref-status"></p>
<p>You can also tap <em>"tap to show/hide reading"</em> on any card to toggle \
it and change the default.</p>
<p>On the <strong>answer side</strong>, the full reading is always shown.</p>
<h3>Tips</h3>
<ul>
  <li>Study one chapter at a time, or shuffle the whole deck</li>
  <li>Cards with related forms show a purple <em>"See also"</em> note</li>
  <li>Suspend this intro card once you've read it</li>
</ul>
</div>
<script>
function setPref(show) {
  try { localStorage.setItem('jlpt_show_reading', show); } catch(e) {}
  updateUI(show);
}
function updateUI(show) {
  document.getElementById('btn-show').className =
    'setting-toggle' + (show ? ' active' : '');
  document.getElementById('btn-hide').className =
    'setting-toggle' + (!show ? ' active' : '');
  document.getElementById('pref-status').textContent =
    show ? 'Reading will be visible on new cards'
         : 'Reading will be hidden on new cards (tap to reveal)';
}
(function() {
  var show;
  try { show = localStorage.getItem('jlpt_show_reading') !== 'false'; }
  catch(e) { show = true; }
  updateUI(show);
})();
</script>
"""

PARENT_NAME = "JLPT N5 Vocabulary"
decks = []
total = 0

intro_deck = genanki.Deck(make_id(f"{PARENT_NAME}::00 — How to use this deck"), f"{PARENT_NAME}::00 — How to use this deck")
intro_note = genanki.Note(
    model=INTRO_MODEL,
    fields=[INTRO_HTML],
    guid=genanki.guid_for("jlpt_n5_intro"),
)
intro_deck.add_note(intro_note)
decks.append(intro_deck)
print("  00 — How to use this deck: 1 intro card")

for chapter_name, entries in CHAPTERS:
    deck_name = f"{PARENT_NAME}::{chapter_name}"
    deck = genanki.Deck(make_id(deck_name), deck_name)
    for entry in entries:
        kanji, reading, romaji, pos, meaning = entry[:5]
        see_also = entry[5] if len(entry) > 5 else ""
        note = genanki.Note(
            model=MODEL,
            fields=[kanji, reading, romaji, pos, meaning, see_also],
            guid=genanki.guid_for(kanji, reading, meaning),
        )
        deck.add_note(note)
    decks.append(deck)
    total += len(entries)
    print(f"  {chapter_name}: {len(entries)} words")

OUTPUT = "jlpt-n5/JLPT_N5_Vocabulary.apkg"
genanki.Package(decks).write_to_file(OUTPUT)
print(f"\nCreated {OUTPUT} with {total} words across {len(CHAPTERS)} chapters (2 card types each = {total * 2} cards)")
