# 椤圭洰鍋ュ悍搴︿慨澶嶄笌鏁欏笀绔秼鍔垮浘瀹炴柦璁″垝

> 璁捐鏂囨。锛歚docs/superpowers/specs/2026-09-26-project-health-and-trend-chart-design.md`锛堟彁浜?`82d2992`锛?> 鍒嗘敮锛歚fix/vite-mobile-connection`锛堜富鐩綍锛?*涓嶄娇鐢?worktree**锛?> 鎵ц鏂瑰紡锛?*鍏ㄩ儴鐢变富浠ｇ悊鐩存帴鎵ц锛屼笉娲惧彂瀛愪唬鐞?*锛堢敤鎴锋槑纭姹傦級
> 鏃ユ湡锛?026-09-26

---

## 鎵ц鍓嶅繀璇?
1. **绔彛鍞竴**锛氭墍鏈夐獙璇佷竴寰嬩娇鐢?`http://localhost:9527/`锛圴ite锛変笌 `http://127.0.0.1:8000`锛團astAPI锛夈€傜姝复鏃剁鍙ｃ€佺姝㈢敓鎴愬叾浠栫綉鍧€銆?2. **棰勮鏃堕棿**锛氭瘡娆℃墽琛岄暱鏃堕棿鍛戒护锛坄typecheck` 绾?2鈥? 鍒嗛挓銆乣build` 绾?3鈥? 鍒嗛挓銆丳laywright 绾?1鈥? 鍒嗛挓锛夊墠锛?*蹇呴』鍏堝悜鐢ㄦ埛澹版槑棰勮鏃堕棿**銆?3. **澶辫触鑷姩閲嶈瘯**锛氬懡浠ゅ洜鐜鎶栧姩澶辫触鏃讹紝鑷姩閲嶈瘯涓€娆★紱杩炵画涓ゆ澶辫触鍒欏仠姝㈠苟鍚戠敤鎴锋姤鍛婏紝涓嶅緱绌鸿浆銆?4. **涓嶄慨鏀逛换浣?`.vtj/files/*.json` DSL 鏂囦欢**銆?5. **鎻愪氦绮掑害**锛氭瘡涓?Task 涓€涓彁浜わ紝绂佹璺?Task 娣峰悎鎻愪氦銆?6. **涓嶆淳鍙戝瓙浠ｇ悊**锛氭湰鏈哄瓙浠ｇ悊涓嶅彲鐢紙涓ゆ瓒呮椂锛夛紝鎵€鏈夊伐浣滅敱涓讳唬鐞嗙洿鎺ユ墽琛屻€?
---

## Task 1锛氬垹闄ゅ绔嬫鏂囦欢锛堥闄╂渶浣庯紝鍏堣寤虹珛淇″績锛?
**鐩爣**锛氭秷闄?37 椤圭被鍨嬮敊璇紝闆惰繍琛屾椂褰卞搷銆?
**Files**
- Delete: `src/vtj/vue/score_analysis.vue`

**渚濇嵁锛堝凡鏍稿疄锛?*
- 鍚?`useProvider({ id: 'score_analysis', version: '1778918611112' })`锛屽睘 VTJ 鐢熸垚鐗┿€?- 涓嶈 `src/router/index.ts`銆乣.vtj/router.js`銆佷换浣曟枃浠?import銆?- `src/vtj/` 鐩綍涓嬩粎姝や竴涓枃浠躲€?- `.vtj/vue/score_analysis.vue` 鏄悓鍔熻兘鍓湰锛堝悓鏍锋湭琚矾鐢憋級锛屼繚鐣欎笉鍔ㄣ€?- 绗?208 琛?`import NavBar from './navbar.vue'` 鏂銆?
- [x] **Step 1锛氬垹闄ゅ墠鏈€鍚庝竴娆＄‘璁ゆ棤寮曠敤**

```powershell
Select-String -Path "src\**\*.ts","src\**\*.vue",".vtj\**\*.js" -Pattern "src/vtj/vue/score_analysis|vtj/vue/score_analysis\.vue"
```

鏈熸湜锛氫粎鍛戒腑 `.vtj/vue/score_analysis.vue` 鑷韩锛坄./vue/score_analysis.vue` 褰㈠紡锛夛紝**涓嶅緱**鍑虹幇 `src/vtj/vue/score_analysis` 瀛楁牱銆傝嫢鍑虹幇浠讳綍寮曠敤锛?*鍋滄骞舵姤鍛?*銆?
- [x] **Step 2锛氳褰曞熀绾块敊璇暟**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | Measure-Object | Select-Object -ExpandProperty Count
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細**78**銆?
- [x] **Step 3锛氬垹闄ゆ枃浠?*

```powershell
git rm -- "src/vtj/vue/score_analysis.vue"
```

- [x] **Step 4锛氶獙璇侀敊璇暟涓嬮檷鍒?41**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | Measure-Object | Select-Object -ExpandProperty Count
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細**41**锛?8 鈭?37锛夈€傝嫢涓嶇锛岃緭鍑哄疄闄呴敊璇竻鍗曞苟鍋滄銆?
- [x] **Step 5锛氭彁浜?*

```powershell
git commit -m "refactor: 鍒犻櫎鏈寮曠敤鐨?score_analysis 瀛ょ珛鍓湰"
```

---

## Task 2锛氳В闄?build 闃绘柇锛坄Tag` 鈫?`PriceTag`锛?
**鐩爣**锛歚vite build` 涓嶅啀鍥犳湭鐭ュ浘鏍囧鍑轰腑鏂€?
**Files**
- Modify: `.vtj/vue/tablet_forum.vue`

**渚濇嵁锛堝凡鏍稿疄锛?*
- `Tag` 鍦?`@vtj/icons@0.16.35` 涓?`0.20.6` 涓潎涓嶅瓨鍦紱44 涓鍏ユ枃浠朵腑浠呮 1 澶勭己澶便€?- 鐪熷疄瀛樺湪鐨勮涔夎繎涔夊鍑猴細`PriceTag`銆乣CollectionTag`銆乣IconTag`銆?- `.vtj/files/tablet_forum.json` 涓?*涓嶅惈** `Tag`锛屾晠鏀?`.vue` 瀹夊叏锛岃璁″櫒閲嶆柊鐢熸垚涓嶄細澶嶇幇銆?- 4 澶勫紩鐢細妯℃澘绗?58 琛?`:icon="Tag"`銆佸鍏ョ 243 琛屻€乣setup()` return 绗?464 琛屻€佸鑸厤缃 270 琛?`icon: Tag`銆?
- [x] **Step 1锛氱‘璁?`PriceTag` 瀛樺湪**

```powershell
node -e "import('@vtj/icons').then(m=>{console.log('PriceTag=',Object.keys(m).includes('PriceTag'))})"
```

鏈熸湜锛歚PriceTag= true`銆?
- [x] **Step 2锛氭浛鎹?4 澶勫紩鐢?*

鍦?`.vtj/vue/tablet_forum.vue` 涓皢 `Tag` 鏇挎崲涓?`PriceTag`锛屾秹鍙婏細
- 瀵煎叆璇彞涓殑 `Tag,` 鈫?`PriceTag,`
- 妯℃澘 `<XIcon :icon="Tag" ...>` 鈫?`:icon="PriceTag"`
- `setup()` return 涓殑 `Tag,` 鈫?`PriceTag,`
- 瀵艰埅閰嶇疆 `icon: Tag` 鈫?`icon: PriceTag`

**娉ㄦ剰**锛氬彧鏇挎崲鐙珛鐨?`Tag` 鏍囪瘑绗︼紝**涓嶅緱**璇激 `hotTags`銆乣searchByTag`銆佹ā鏉夸腑 `v-for="(tag, index) in hotTags"`銆乣@click="searchByTag(tag)"` 绛夊惈 `Tag` 瀛愪覆鐨勬爣璇嗙銆?
- [x] **Step 3锛氱‘璁ゆ棤娈嬬暀**

```powershell
Select-String -Path ".vtj\vue\tablet_forum.vue" -Pattern "\bTag\b" -AllMatches
```

鏈熸湜锛氭棤鍖归厤锛堟垨浠呭尮閰嶅埌宸叉敼涓?`PriceTag` 涔嬪鐨勭湡瀹為渶姹傗€斺€旇嫢鏈夐渶浜哄伐纭锛夈€?
- [x] **Step 4锛氶獙璇?build 閫氳繃**

```powershell
npm run build
```

棰勮鏃堕棿锛氱害 3鈥? 鍒嗛挓銆傛湡鏈涳細鏋勫缓瀹屾垚锛屼笉鍐嶅嚭鐜?`"Tag" is not exported`銆傝嫢鍑虹幇**鍏朵粬**鍥炬爣缂哄け閿欒锛岃鏄庡瓨鍦ㄦ湰杞湭鍙戠幇鐨勭己澶卞鍑猴紝闇€閲嶆柊鍏ㄩ噺鎵弿鍚庡啀缁х画銆?
- [x] **Step 5锛氭彁浜?*

```powershell
git add -- ".vtj/vue/tablet_forum.vue"
git commit -m "fix: 鐢?PriceTag 鏇挎崲涓嶅瓨鍦ㄧ殑 Tag 鍥炬爣"
```

---

## Task 3锛氬悗绔柊澧炲垎鐝骇瓒嬪娍搴忓垪

**鐩爣**锛歚/analytics/overview` 杩斿洖 `class_trend`锛屽苟椤哄甫淇?N+1 鏌ヨ涓庢棩鏈熼敭纰版挒銆?
**Files**
- Modify: `backend/app/schemas/teacher.py`锛堢 329 琛岄檮杩戯級
- Modify: `backend/app/api/v1/teacher.py`锛堢 1684鈥?766 琛?`get_analytics_overview`锛?
**渚濇嵁锛堝凡鏍稿疄锛?*
- 瀛︾敓涓庣彮绾у敮涓€鍏宠仈鏄?`SysUser.class_name` **瀛楃涓?*锛屾棤 `class_id` 澶栭敭銆?- 鐜版湁 `score_trend` 浠?`%m-%d` 涓洪敭锛堣法鏈?璺ㄥ勾浼氶潤榛樺悎骞讹級锛屽繀椤讳慨姝ｃ€?- 绗?1742 琛?`db.query(ExamPaper).filter(ExamPaper.paper_id == r.paper_id).first()` 浣嶄簬閬嶅巻 `records` 鐨勫惊鐜綋鍐咃紙姣忔潯璁板綍涓€娆℃煡璇級銆?
- [x] **Step 1锛氭柊澧?schema**

鍦?`backend/app/schemas/teacher.py` 鐨?`AnalyticsOverview` 涔嬪墠鎻掑叆锛?
```python
class ClassTrendPoint(BaseModel):
    """鐝骇瓒嬪娍鍗曠偣"""
    date: str          # 杈撳嚭鏍煎紡 "09-01"
    avg_score: float


class ClassTrendSeries(BaseModel):
    """鐝骇鎴愮哗瓒嬪娍搴忓垪"""
    class_id: Optional[int] = None
    class_name: str
    points: List[ClassTrendPoint] = []
```

骞剁‘璁?`AnalyticsOverview` 鏂板瀛楁锛?
```python
    class_trend: List[ClassTrendSeries] = []
```

鍚屾椂纭鏂囦欢宸插鍏?`Optional` 涓?`List`锛坄teacher.py` 涓凡鍦ㄧ敤锛屽簲鏃犻渶鏂板锛夈€?
- [x] **Step 2锛氫慨澶嶆棩鏈熼敭涓?N+1 鏌ヨ**

鍦?`get_analytics_overview` 涓細

1. 灏?`date_scores` 鐨勯敭鐢?`r.start_time.strftime("%m-%d")` 鏀逛负瀹屾暣鍙帓搴忛敭 `%Y-%m-%d`锛屾帓搴忓悗鍐嶆牸寮忓寲涓?`%m-%d` 杈撳嚭锛屼繚鎸?`score_trend` 瀵瑰缁撴瀯涓嶅彉銆?2. 灏嗙 1742 琛屽惊鐜綋鍐呯殑閫愭潯 `ExamPaper` 鏌ヨ鏀逛负锛氬惊鐜涓€娆℃€ф敹闆嗗叏閮?`paper_id`锛屾壒閲忔煡璇㈠悗鏋勫缓 `paper_id -> subject_id` 鏄犲皠锛屽惊鐜唴鏀逛负鏌ヨ〃銆?
- [x] **Step 3锛氭柊澧炲垎鐝骇鑱氬悎**

鍦ㄥ悓涓€鍑芥暟涓紝淇濇寔 `score_trend` 鍘熸牱锛屾柊澧炲垎鐝骇鑱氬悎锛?
- 淇濈暀 `class_names`锛堟暀甯堝叏閮ㄧ彮绾э級涓庤 `class_id` 杩囨护鍚庣殑鍒嗘敮閫昏緫銆?- 瀵规瘡涓彮绾у悕鏌ュ嚭鍏?`user_id` 闆嗗悎锛坄SysUser.class_name == 鐝骇鍚峘 涓?`user_type == 'student'`锛夈€?- 澶嶇敤宸叉煡璇㈢殑 `records`锛屾寜 `user_id -> class_name` 鏄犲皠鍒嗙粍銆?- 姣忕彮鎸夊畬鏁存棩鏈熼敭鑱氬悎骞冲潎鍒嗭紝鎺掑簭鍚庢牸寮忓寲涓?`%m-%d`锛岃緭鍑?`ClassTrendSeries`锛坄class_id` 閫氳繃 `Banji` 鎸?`class_name` 鍙嶆煡濉厖锛屾煡涓嶅埌鍒欎负 `None`锛夈€?- 鏌愮彮鏃犱换浣曡褰曟椂**涓嶈緭鍑?*璇ョ彮搴忓垪锛堥伩鍏嶇┖鎶樼嚎锛夈€?
- [x] **Step 4锛氶獙璇佸悗绔彲瀵煎叆涓斿搷搴旂粨鏋勫悎娉?*

```powershell
cd backend; python -c "from app.schemas.teacher import AnalyticsOverview, ClassTrendSeries; print(AnalyticsOverview().model_dump().keys())"
```

鏈熸湜锛氳緭鍑哄寘鍚?`class_trend` 鐨勯敭鍒楄〃銆?
- [x] **Step 5锛氶獙璇佹帴鍙ｅ搷搴?*

鍚姩鍚庣鍚庯紝鐢ㄦ暀甯堣处鍙?token 璋冪敤锛?
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/teacher/analytics/overview?days=30" -Headers @{ Authorization = "Bearer <token>" }
```

鏈熸湜锛?- `score_trend` 缁撴瀯涓庢敼鍔ㄥ墠涓€鑷达紙`dates` + `scores`锛夛紱
- `class_trend` 涓烘暟缁勶紝姣忛」鍚?`class_id`銆乣class_name`銆乣points`锛屾瘡涓?point 鍚?`date`锛坄%m-%d`锛変笌 `avg_score`锛?- 甯?`?class_id=<鐪熷疄id>` 鏃朵粎杩斿洖璇ョ彮搴忓垪銆?
- [x] **Step 6锛氭彁浜?*

```powershell
git add -- "backend/app/schemas/teacher.py" "backend/app/api/v1/teacher.py"
git commit -m "feat: 瀛︽儏鎬昏鏂板鍒嗙彮绾ц秼鍔垮苟淇 N+1 鏌ヨ涓庢棩鏈熼敭"
```

---

## Task 4锛氬墠绔秼鍔垮浘瀹屾暣瀹炵幇

**鐩爣**锛氫慨澶嶇瓫閫変笅鎷夋澶辨晥锛屽疄鐜扮湡瀹炴覆鏌撳鐝骇鎶樼嚎鐨勮秼鍔垮浘锛屾秷闄?22 椤圭被鍨嬮敊璇€?
**Files**
- Modify: `.vtj/vue/teacher_analytics.vue`

**渚濊禆**锛?*蹇呴』鍦?Task 3 涔嬪悗鎵ц**锛堥渶瑕?`overview.class_trend` 瀛楁锛夈€?
**渚濇嵁锛堝凡鏍稿疄锛?*
- `loadData` 瀹氫箟浜庣 190 琛岋紝浣?`setup()` return锛堢 287鈥?92 琛岋級**涓嶅惈**瀹?鈫?妯℃澘 `@change="loadData"` 杩愯鏃朵负 `undefined`銆?- 8 涓秼鍔跨粦瀹氬湪妯℃澘琚紩鐢ㄤ絾鑴氭湰涓畬鍏ㄤ笉瀛樺湪銆?- `trendData`锛堢 167 琛?`ref<any[]>([])`锛変粠鏈濉厖銆?
- [x] **Step 1锛氱‘璁ゅ綋鍓嶉敊璇竻鍗?*

```powershell
npm run typecheck 2>&1 | Select-String "teacher_analytics"
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細22 琛屻€?
- [x] **Step 2锛氭妸 `loadData` 鍔犲叆 `setup()` return**

鍦?return 鍧楋紙绗?287鈥?92 琛岋級涓ˉ鍏?`loadData`銆?
- [x] **Step 3锛氬～鍏?`trendData`**

鍦?`loadData()` 涓紝`overviewData` 瑙ｆ瀽鎴愬姛鍚庯紝鍙?`overviewData.class_trend`锛涜嫢缂哄け鎴栦负绌猴紝鍒欓檷绾т负鍗曞簭鍒楋細

```typescript
const series = Array.isArray(overviewData.class_trend) && overviewData.class_trend.length
  ? overviewData.class_trend
  : [{ class_name: '骞冲潎鍒?, points: (overviewData.score_trend?.dates ?? []).map((d, i) => ({ date: d, avg_score: overviewData.score_trend.scores[i] })) }];
trendData.value = series;
```

- [x] **Step 4锛氬疄鐜?8 涓秼鍔胯绠楀睘鎬?*

鍦?`setup()` 鍐呯敤 `computed` 瀹炵幇骞跺姞鍏?return锛?
| 缁戝畾 | 瀹炵幇瑕佺偣 |
| --- | --- |
| `trendSvgWidth` | 甯搁噺锛屽缓璁?`640` |
| `trendSvgHeight` | 甯搁噺锛屽缓璁?`260` |
| `trendYTicks` | 鐢卞叏灞€鍒嗘暟鍊煎煙绛夊垎鐢熸垚锛堝惈 0 涓庝笂鐣岋紝涓婄晫鍚戜笂鍙栨暣鍒?10 鐨勫€嶆暟锛?|
| `trendY(tick)` | 鍒诲害鍊?鈫?鍍忕礌 Y锛涢渶涓?`trendYTicks` 鐢熸垚瑙勫垯涓ユ牸浜掗€?|
| `trendPoints` | 鍏ㄩ儴鐝骇搴忓垪鏃ユ湡鐨勫苟闆嗭紝鎸夊簭鍘婚噸 鈫?`{ label: date }[]` |
| `trendX(i)` | 绱㈠紩 鈫?鍍忕礌 X锛涢渶澶勭悊鍗曠偣涓庣┖鏁扮粍涓ょ杈圭晫锛堣繑鍥炶酱涓偣 / 0锛?|
| `trendLines` | 姣忕彮绾т竴鏉★細`{ name: class_name, points: 'x,y x,y ...', dots: [{x,y}] }` |
| `trendColors` | 鍥哄畾璋冭壊鏉垮瓧绗︿覆鏁扮粍 |

**鍏抽敭杈圭晫**锛歚trendData` 涓虹┖鏁扮粍鏃讹紝`trendLines`/`trendPoints`/`trendYTicks` 蹇呴』杩斿洖绌烘暟缁勬垨瀹夊叏榛樿鍊硷紝涓?`trendY`/`trendX` 鍦ㄨ璋冪敤鏃朵笉寰楁姏寮傚父锛堟ā鏉?`v-for` 铏戒細璺宠繃锛屼絾 `trendX` 鍦?`trendPoints` 涓虹┖鏃朵笉浼氳璋冪敤锛屼粛闇€闃插尽锛夈€?
鏌愮彮绾у湪鏌愭棩鏈熸棤鏁版嵁鏃?*璺宠繃璇ョ偣**锛屼笉琛?0銆?
- [x] **Step 5锛氶獙璇侀敊璇竻闆?*

```powershell
npm run typecheck 2>&1 | Select-String "teacher_analytics"
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細**鏃犺緭鍑?*銆?
- [x] **Step 6锛氳繍琛屾椂楠岃瘉**

鐢?Playwright 绉诲姩瑙嗗彛锛?90脳844锛夎闂?`http://localhost:9527/`锛屼互鏁欏笀璐﹀彿 `ycc5678 / ycc5678` 鐧诲綍鍚庤繘鍏ユ暀甯堝垎鏋愰〉锛岀‘璁わ細
- 鐝骇/绉戠洰涓嬫媺妗嗗垏鎹㈠悗鏁版嵁鍒锋柊锛堢瓫閫夌湡姝ｇ敓鏁堬級锛?- 瓒嬪娍鍥炬覆鏌撳嚭**澶氭潯**鐝骇鎶樼嚎涓庡浘渚嬶紱
- 鎺у埗鍙版棤璇ラ〉鐩稿叧鐨勬姤閿欍€?
- [x] **Step 7锛氭彁浜?*

```powershell
git add -- ".vtj/vue/teacher_analytics.vue"
git commit -m "fix: 淇瀛︽儏鍒嗘瀽椤电瓫閫夊け鏁堝苟瀹炵幇鍒嗙彮绾ц秼鍔垮浘"
```

---

## Task 5锛氳ˉ榻愮被鍨嬪０鏄庝笌鏀剁獎锛?4 椤圭湡瀹為敊璇級

**鐩爣**锛氭秷闄?TS7016锛? 椤癸級銆乀S18046锛? 椤癸級銆乀S2365/TS2345/TS7015锛? 椤癸級绛夌湡瀹炵被鍨嬮敊璇€?
**Files**
- Create: `src/utils/questionRender.d.ts`
- Modify: `src/router/index.ts`
- Modify: `.vtj/vue/teacher_profile.vue`
- Modify: `.vtj/vue/TeacherNavHeader.vue`
- Modify: `src/views/help.vue`
- Modify: `src/views/mobile_answer.vue`
- Modify: `src/views/mobile_news.vue`

**渚濊禆**锛?*蹇呴』鍦?Task 1 涔嬪悗**锛堝惁鍒欏熀绾挎暟瀛椾笉鍑嗭級銆?
- [x] **Step 1锛氬厛璇?`questionRender.js` 纭瀵煎嚭绛惧悕**

```powershell
Select-String -Path "src\utils\questionRender.js" -Pattern "^export|module.exports"
```

鎹疄闄呭鍑虹紪鍐?`.d.ts`锛?*涓嶅緱鍑┖鐚滄祴绛惧悕**銆傝嫢瀵煎嚭澶氫釜鍑芥暟锛岄€愪竴澹版槑銆?
- [x] **Step 2锛氭柊澧?`src/utils/questionRender.d.ts`**

鎸?Step 1 鐨勭湡瀹炵鍚嶅０鏄庛€傛秷闄?`teacher_analytics:153`銆乣teacher_papers:364`銆乣mobile_answer:58` 涓夊 TS7016銆?
- [x] **Step 3锛氫慨 `src/router/index.ts` 鐨勪袱澶?TS7016**

绗?51銆?7 琛屽鍏?`@/views/exercise.vue`銆乣@/views/solution.vue`銆備袱鏂囦欢鍧囧瓨鍦ㄤ絾缂哄０鏄庘€斺€旀鏌?`src/env.d.ts` 涓凡鏈夌殑 `declare module '*.vue'` 鍙樹綋涓轰綍鏈鐩?`@/` 鍒悕璺緞锛涘纭涓哄埆鍚嶈矾寰勬湭琚€氶厤绗﹀尮閰嶏紝鍦?`src/env.d.ts` 涓ˉ鍏呭尮閰?`@/*.vue` 鐨勫０鏄庢ā鍧楋紙**浼樺厛鏀?`env.d.ts` 鑰岄潪鍦?router 鍐呭姞 `// @ts-ignore`**锛夈€?
- [x] **Step 4锛氫慨涓ゅ `$refs` TS18046**

`.vtj/vue/teacher_profile.vue:9` 鐨?`$refs.avatarInput`銆乣.vtj/vue/TeacherNavHeader.vue:74` 鐨?`$refs.profileAvatarInput`銆備娇鐢?Vue 3.5 鐨?`useTemplateRef` 鑾峰緱鏄惧紡绫诲瀷锛屽苟淇濇寔杩愯鏃惰涓轰笌 `$refs` 瀹屽叏涓€鑷淬€?
- [x] **Step 5锛氭敹绐勮矾鐢卞弬鏁?*

`src/views/help.vue:14`銆乣src/views/mobile_answer.vue:32,33,35`銆乣src/views/mobile_news.vue:33`銆傚皢 `route.params.x`锛堢被鍨?`string | string[]`锛夋樉寮忚浆涓?`number`锛岀敤 `Number(...)` 骞舵牎楠?`Number.isNaN`锛?*涓嶅緱**鐢?`as number` 纭柇瑷€鎺╃洊銆?
- [x] **Step 6锛氶獙璇侀敊璇竻闆?*

```powershell
npm run typecheck 2>&1 | Select-String "error TS"
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細**浠呭墿 8 琛岋紝涓斿叏閮ㄤ负 `.vtj/vue/teacher_papers.vue`**銆?
- [x] **Step 7锛氭彁浜?*

```powershell
git add -- "src/utils/questionRender.d.ts" "src/env.d.ts" "src/router/index.ts" ".vtj/vue/teacher_profile.vue" ".vtj/vue/TeacherNavHeader.vue" "src/views/help.vue" "src/views/mobile_answer.vue" "src/views/mobile_news.vue"
git commit -m "fix: 琛ラ綈绫诲瀷澹版槑骞舵敹绐勮矾鐢卞弬鏁颁笌妯℃澘寮曠敤"
```

---

## Task 6锛欳SP 鏀惧紑鍥炬爣瀛椾綋

**鐩爣**锛氭秷闄?4 鏉?`font-src` CSP 杩濊銆?
**Files**
- Modify: `index.html`锛堢 12 琛岋級

- [x] **Step 1锛氫慨鏀?CSP**

```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' ws: wss:; img-src 'self' data:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:;" />
```

- [x] **Step 2锛氳繍琛屾椂楠岃瘉**

Playwright 璁块棶 `http://localhost:9527/`锛屾鏌ユ帶鍒跺彴娑堟伅涓?`violates the following Content Security Policy` 鏁伴噺銆?
棰勮鏃堕棿锛氱害 1鈥? 鍒嗛挓銆傛湡鏈涳細**0 鏉?*銆?
- [x] **Step 3锛氭彁浜?*

```powershell
git add -- "index.html"
git commit -m "fix: CSP 鏀惧紑 data 瀛椾綋浠ュ姞杞?VTJ 鍥炬爣瀛椾綋"
```

---

## Task 7锛氬缓绔?typecheck 閿欒鍩虹嚎

**鐩爣**锛氬湪浠呭墿 8 椤?codegen 鍣煶鏃跺浐鍖栧熀绾匡紝浣滀负瀹堝崼鐨勫垽瀹氫緷鎹€?
**Files**
- Create: `.typecheck-baseline.json`
- Create: `scripts/verify-typecheck-baseline.mjs`锛堣В鏋愪笌姣斿閫昏緫锛孴ask 8 澶嶇敤锛?
**渚濊禆**锛?*蹇呴』鍦?Task 1銆? 涔嬪悗**銆?
- [x] **Step 1锛氱‘璁ゆ畫浣欓敊璇伆涓?8 椤逛笖鍏ㄥ湪 teacher_papers.vue**

```powershell
npm run typecheck 2>&1 | Select-String "error TS" | ForEach-Object { ($_ -split '\(')[0] } | Group-Object | Format-Table Count,Name
```

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細鍗曚竴鍒嗙粍 `8 .vtj/vue/teacher_papers.vue`銆?*鑻ュ嚭鐜颁换浣曞叾浠栨枃浠讹紝绔嬪嵆鍋滄骞跺洖鍒?Task 5銆?*

- [x] **Step 2锛氱紪鍐欏熀绾胯В鏋愪笌姣斿鑴氭湰**

`scripts/verify-typecheck-baseline.mjs`锛?
- 鎵ц `vue-tsc --noEmit -p tsconfig.json`锛堥€氳繃 `spawn` 璋冪敤 `node node_modules/vue-tsc/bin/vue-tsc.js`锛夈€?- 瑙ｆ瀽 `鏂囦欢(琛?鍒?: error TSxxxx: 娑堟伅`锛屽綊涓€鍖栦负 `{ file, line, code }`锛?*涓㈠純鍒楀彿涓庢秷鎭鏂?*銆?- 璇诲彇 `.typecheck-baseline.json`锛涗笉瀛樺湪鏃舵寜銆岄娆″缓绔嬪熀绾裤€嶅鐞嗭細鍐欏嚭鍩虹嚎銆佹墦鍗版彁绀恒€侀€€鍑虹爜 0銆?- 瀛樺湪鏃跺仛闆嗗悎宸泦锛歚鏂板 = 褰撳墠 鈭?鍩虹嚎`銆乣宸叉秷澶?= 鍩虹嚎 鈭?褰撳墠`銆?- `鏂板` 闈炵┖ 鈫?鎵撳嵃鏂板鏉＄洰骞朵互閫€鍑虹爜 1 澶辫触锛涘惁鍒欐墦鍗般€屽凡娑堝け銆嶆潯鐩綔涓烘竻鐞嗘彁绀猴紝閫€鍑虹爜 0銆?- 鍏煎 Windows 涓?`vue-tsc` 鐨?CRLF 杈撳嚭涓庝腑鏂囪矾寰勩€?
- [x] **Step 3锛氱敓鎴愬熀绾挎枃浠?*

```powershell
node scripts/verify-typecheck-baseline.mjs
```

鏈熸湜锛氬垱寤?`.typecheck-baseline.json`锛宍totalErrors: 8`锛屽叏閮ㄦ潯鐩?`file: ".vtj/vue/teacher_papers.vue"`銆?
- [x] **Step 4锛氶獙璇佸箓绛?*

鍐嶆鎵ц鍚屽懡浠わ紝鏈熸湜閫€鍑虹爜 0 涓旀姤鍛娿€岄浂鏂板銆嶃€?
- [x] **Step 5锛氶獙璇佽兘鎹曡幏鏂伴敊璇?*

涓存椂鍦ㄦ煇涓彈 `tsconfig` 绠¤緰鐨勬枃浠朵腑寮曞叆涓€澶勭被鍨嬮敊璇紝鎵ц鍩虹嚎鑴氭湰锛屾湡鏈涢€€鍑虹爜 1 骞跺噯纭寚鍑鸿鏉＄洰锛涢殢鍚庢挙閿€璇ヤ复鏃堕敊璇紝鍐嶆鎵ц纭鎭㈠閫€鍑虹爜 0銆?
- [x] **Step 6锛氭彁浜?*

```powershell
git add -- ".typecheck-baseline.json" "scripts/verify-typecheck-baseline.mjs"
git commit -m "test: 寤虹珛 typecheck 閿欒鍩虹嚎骞舵柊澧炲熀绾挎牎楠岃剼鏈?
```

---

## Task 8锛氱粺涓€瀹堝崼鑴氭湰锛堝洓绫绘鏌ワ級

**鐩爣**锛氫竴涓?`scripts/verify-project-health.mjs` 瑕嗙洊鍥炬爣瀵煎叆銆乼ypecheck 鍩虹嚎銆佸绔嬫枃浠躲€佺増鏈紓绉伙紝鎺ュ叆 `prebuild`銆?
**Files**
- Create: `scripts/verify-project-health.mjs`
- Modify: `package.json`锛堟柊澧?`verify:health` 涓?`prebuild`锛?
**渚濊禆**锛?*蹇呴』鍦?Task 7 涔嬪悗**锛堝鐢ㄥ熀绾块€昏緫锛夈€?
- [x] **Step 1锛氬疄鐜版鏌?1 鈥斺€?鍥炬爣瀵煎叆鍚堟硶鎬э紙闃绘柇锛?*

- 閫掑綊閬嶅巻 `.vtj/vue/**` 涓?`src/**` 涓?`.vue`銆?- 姝ｅ垯**蹇呴』**鐢?`import\s*\{([^}]*)\}\s*from\s*['"]@vtj\/icons['"]`銆?  **涓ョ**浣跨敤 `[\s\S]*?` 绛夎椽濠?璺ㄨ鍙ュ啓娉曗€斺€斿凡瀹炴祴浼氳法瓒婂涓?import 璇彞浜х敓澶ч噺璇姤銆?- 涓?`await import('@vtj/icons')` 鐨勮繍琛屾椂瀵煎嚭闆嗘瘮瀵广€?- 鏈煡鍥炬爣鏃舵寜銆屽寘鍚叧绯?+ 缂栬緫璺濈銆嶄粠瀵煎嚭闆嗕腑鎺ㄨ崘鏈€澶?3 涓€欓€夛紝涓€骞舵墦鍗般€?
- [x] **Step 2锛氬疄鐜版鏌?2 鈥斺€?澶嶇敤 Task 7 鐨勫熀绾挎瘮瀵癸紙闃绘柇锛?*

瀵煎叆 `scripts/verify-typecheck-baseline.mjs` 瀵煎嚭鐨勬瘮瀵瑰嚱鏁帮紝閬垮厤閫昏緫閲嶅銆?
- [x] **Step 3锛氬疄鐜版鏌?3 鈥斺€?瀛ょ珛鏂囦欢鎵弿锛堣鍛婏級**

- 鏀堕泦 `src/router/index.ts` 涓?`.vtj/router.js` 涓嚭鐜扮殑鎵€鏈?`.vue` 璺緞寮曠敤锛堝悓鏃惰瘑鍒?`@/views/x.vue`銆乣$vtj/vue/x.vue`銆乣./vue/x.vue` 涓夌褰㈠紡锛夈€?- 鎵弿 `src/**`銆乣.vtj/vue/**` 涓?`.vue`锛屾湭琚紩鐢ㄨ€呰緭鍑?*璀﹀憡**銆?- **涓嶅緱**鍥犳澶辫触锛歏TJ `Provider` 鍙敞鍐屽姩鎬?`/page/:id` 璺敱銆?
- [x] **Step 4锛氬疄鐜版鏌?4 鈥斺€?VTJ 鐗堟湰婕傜Щ锛堣鍛婏級**

- 瀵瑰惈 `useProvider(` 涓斿甫 `version: 'N'` 鐨?`.vtj/vue/*.vue`锛屽彇 `N` 涓?`.vtj/files/<鍚屽悕>.json` 鐨?`__VERSION__` 姣斿銆?- 涓嶄竴鑷磋緭鍑?*璀﹀憡**锛屾枃妗堥渶鐐规槑銆屾墜鏀逛細鍦ㄨ璁″櫒淇濆瓨鏃惰瑕嗙洊銆嶃€?- DSL 鏂囦欢涓嶅瓨鍦ㄦ椂璺宠繃骞舵彁绀恒€?
- [x] **Step 5锛氭眹鎬昏緭鍑轰笌閫€鍑虹爜**

闃绘柇绫伙紙妫€鏌?1銆?锛変换涓€澶辫触 鈫?閫€鍑虹爜 1锛涗粎璀﹀憡锛堟鏌?3銆?锛夆啋 閫€鍑虹爜 0銆傝緭鍑洪渶鍒嗚妭娓呮櫚銆佸惈鏂囦欢璺緞涓庡缓璁姩浣溿€?
- [x] **Step 6锛氭帴鍏?`package.json`**

```json
"verify:health": "node scripts/verify-project-health.mjs",
"prebuild": "node scripts/verify-project-health.mjs"
```

娉ㄦ剰锛歚prebuild` 浼氬湪 `npm run build` 鍓嶈嚜鍔ㄦ墽琛屻€傜‘璁ょ幇鏈?`build` 閾撅紙`build` 鈫?`build:prod` 鈫?`vue-tsc && vite build`锛変笉琚牬鍧忋€?
- [x] **Step 7锛氭鍚戦獙璇?*

```powershell
npm run verify:health
```

鏈熸湜锛氶€€鍑虹爜 0锛涙鏌?1銆? 閫氳繃锛涙鏌?3銆? 杈撳嚭璀﹀憡锛堝綋鍓嶅簲鑳芥姤鍑哄绔嬫枃浠朵笌鍙兘鐨勭増鏈紓绉伙級銆?
- [x] **Step 8锛氬弽鍚戦獙璇侊紙闃绘柇鏈夋晥鎬э級**

涓存椂鎶?`.vtj/vue/tablet_forum.vue` 鐨?`PriceTag` 鏀瑰洖 `Tag`锛屾墽琛?`npm run verify:health`锛屾湡鏈涢€€鍑虹爜 1 骞舵彁绀?`Tag` 涓庡€欓€?`PriceTag`/`CollectionTag`/`IconTag`锛涢殢鍚庢敼鍥炪€?
- [x] **Step 9锛氭彁浜?*

```powershell
git add -- "scripts/verify-project-health.mjs" "package.json"
git commit -m "test: 鏂板椤圭洰鍋ュ悍搴︾粺涓€瀹堝崼骞舵帴鍏?prebuild"
```

---

## Task 9锛氬叏閲忛獙璇佷笌鏂囨。鏀跺熬

**鐩爣**锛氫簲椤归獙璇佹爣鍑嗗叏閮ㄩ€氳繃锛屾洿鏂版柟妗堟枃妗ｃ€?
- [x] **Step 1锛歚npm run verify:health`**

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓锛堝唴鍚?typecheck锛夈€傛湡鏈涳細閫€鍑虹爜 0銆?
- [x] **Step 2锛歚npm run typecheck`**

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傛湡鏈涳細闆舵柊澧為敊璇€?
- [x] **Step 3锛歚npm run build`**

棰勮鏃堕棿锛氱害 3鈥? 鍒嗛挓銆傛湡鏈涳細绔埌绔畬鎴愩€?
- [x] **Step 4锛歚npm run test:vite-resilience`**

棰勮鏃堕棿锛氱害 1鈥? 鍒嗛挓銆傛湡鏈涳細`PASS vite resilience: ws proxy, 50 resets, strictPort, backend outage`銆?
- [x] **Step 5锛歅laywright 绉诲姩瑙嗗彛鍥炲綊**

棰勮鏃堕棿锛氱害 2鈥? 鍒嗛挓銆傝鍙?390脳844锛岃闂?`http://localhost:9527/`锛岀‘璁わ細
- 椤甸潰姝ｅ父娓叉煋锛屾棤銆屼竴鐩村姞杞姐€嶏紱
- 鏁欏笀鍒嗘瀽椤电瓫閫夊彲鐢ㄣ€佽秼鍔垮浘娓叉煋澶氱彮绾ф姌绾匡紱
- `/tablet/forum` 姝ｅ父鍔犺浇锛?- 鎺у埗鍙?**0 鏉?* CSP 杩濊銆?
- [x] **Step 6锛欸it 鏍搁獙**

```powershell
git status --short --branch
git log --oneline <Task1鍓峜ommit>..HEAD
git diff --name-only <Task1鍓峜ommit>..HEAD
```

纭锛氭棤 `.vtj/files/*.json` 鍙樻洿锛涙棤 `tsconfig*.json` 鍙樻洿锛涙棤鍚庣鏁版嵁搴撴ā鍨嬪彉鏇达紱浠呴鍏堝瓨鍦ㄧ殑鏈窡韪」锛坄.vtj/files/*.bak`銆乣backend/app/uploads/avatars/`锛変繚鎸佹湭鎻愪氦銆?
- [x] **Step 7锛氭洿鏂版柟妗堟枃妗?*

鍦?`solve_problems_files/Vite浠ｇ悊娣诲姞閿欒澶勭悊鏂规.md` 鎴栨柊寤哄綊妗ｆ枃妗ｄ腑璁板綍鏈疆淇缁撴灉銆侀獙璇佽瘉鎹€侀敊璇暟鍙樺寲杞ㄨ抗锛?8 鈫?41 鈫?19 鈫?8 鈫?鍩虹嚎锛変笌鎻愪氦娓呭崟銆?
- [x] **Step 8锛氭彁浜ゆ枃妗?*

```powershell
git add -- "solve_problems_files/" "docs/superpowers/plans/2026-09-26-project-health-and-trend-chart.md"
git commit -m "docs: 璁板綍椤圭洰鍋ュ悍搴︿慨澶嶉獙璇佽瘉鎹?
```

- [x] **Step 9锛氬嬀閫夎鍒掔姸鎬?*

灏嗘湰璁″垝鏂囦欢鎵€鏈?`- [x]` 鏇存柊涓?`- [x]`锛屽崟鐙彁浜わ細

```powershell
git add -- "docs/superpowers/plans/2026-09-26-project-health-and-trend-chart.md"
git commit -m "docs: 鏍囪瀹炴柦璁″垝瀹屾垚鐘舵€?
```

---

## 閿欒鏁板彉鍖栬建杩癸紙棰勬湡锛?
| 闃舵 | 閿欒鏁?| 璇存槑 |
| --- | ---: | --- |
| 鍒濆 | 78 | 瀹炴祴鍩虹嚎 |
| Task 1 鍚?| 41 | 鍒犻櫎瀛ょ珛姝绘枃浠讹紙鈭?7锛?|
| Task 4 鍚?| 19 | 瓒嬪娍鍥句笌 `loadData`锛堚垝22锛?|
| Task 5 鍚?| 8 | 绫诲瀷澹版槑銆乣$refs`銆佽矾鐢卞弬鏁帮紙鈭?1锛屽彟 +1 璁″叆鍙ｅ緞宸紓锛?|
| Task 7 鍚?| 8 | 鍥哄寲涓哄熀绾匡紝涓嶅啀涓嬮檷 |

## 鎻愪氦娓呭崟锛堥鏈?9 涓級

| # | 鎻愪氦淇℃伅 |
| --- | --- |
| 1 | `refactor: 鍒犻櫎鏈寮曠敤鐨?score_analysis 瀛ょ珛鍓湰` |
| 2 | `fix: 鐢?PriceTag 鏇挎崲涓嶅瓨鍦ㄧ殑 Tag 鍥炬爣` |
| 3 | `feat: 瀛︽儏鎬昏鏂板鍒嗙彮绾ц秼鍔垮苟淇 N+1 鏌ヨ涓庢棩鏈熼敭` |
| 4 | `fix: 淇瀛︽儏鍒嗘瀽椤电瓫閫夊け鏁堝苟瀹炵幇鍒嗙彮绾ц秼鍔垮浘` |
| 5 | `fix: 琛ラ綈绫诲瀷澹版槑骞舵敹绐勮矾鐢卞弬鏁颁笌妯℃澘寮曠敤` |
| 6 | `fix: CSP 鏀惧紑 data 瀛椾綋浠ュ姞杞?VTJ 鍥炬爣瀛椾綋` |
| 7 | `test: 寤虹珛 typecheck 閿欒鍩虹嚎骞舵柊澧炲熀绾挎牎楠岃剼鏈琡 |
| 8 | `test: 鏂板椤圭洰鍋ュ悍搴︾粺涓€瀹堝崼骞舵帴鍏?prebuild` |
| 9 | `docs: 璁板綍椤圭洰鍋ュ悍搴︿慨澶嶉獙璇佽瘉鎹甡锛? 璁″垝鍕鹃€夋彁浜わ級 |
