from collections import defaultdict, deque


def _persona(
    key: str,
    name: str,
    faction: str,
    summary: str,
    traits: list[str],
    motivations: list[str],
) -> dict:
    return {
        "key": key,
        "name": name,
        "aliases": [],
        "faction": faction,
        "summary": summary,
        "traits": traits,
        "motivations": motivations,
        "values": [],
        "abilities": [],
        "communication": [],
        "background": "",
    }


def _template(
    *,
    template_id: str,
    name: str,
    theme: str,
    world_type: str,
    description: str,
    personas: list[dict],
    relationships: list[dict],
) -> dict:
    return {
        "id": template_id,
        "name": name,
        "theme": theme,
        "world_type": world_type,
        "version": "1.0.0",
        "description": description,
        "source": "curated",
        "personas": personas,
        "relationships": relationships,
    }


ROMANCE_PERSONAS = [
    _persona("liu_bei", "刘备", "蜀汉", "以复兴汉室为号召的政治领袖。", ["仁厚", "坚韧"], ["建立基业", "延续汉统"]),
    _persona("guan_yu", "关羽", "蜀汉", "重义守信、威望卓著的将领。", ["忠义", "自负"], ["辅佐刘备", "维护声名"]),
    _persona("zhang_fei", "张飞", "蜀汉", "勇猛直率而性情急烈的将领。", ["勇猛", "急躁"], ["保护同伴", "建功"]),
    _persona("zhuge_liang", "诸葛亮", "蜀汉", "擅长谋划与治理的军师。", ["谨慎", "克制"], ["稳定政权", "完成托付"]),
    _persona("cao_cao", "曹操", "曹魏", "雄才多疑、善于用人的枭雄。", ["果断", "多疑"], ["统一天下", "掌控局势"]),
    _persona("sima_yi", "司马懿", "曹魏", "善于隐忍和长期布局的重臣。", ["隐忍", "审慎"], ["保存实力", "扩大影响"]),
    _persona("sun_quan", "孙权", "东吴", "善于平衡臣属与联盟的统治者。", ["务实", "权衡"], ["守住江东", "扩张利益"]),
    _persona("zhou_yu", "周瑜", "东吴", "才华出众、维护江东利益的统帅。", ["敏锐", "骄傲"], ["击败强敌", "巩固江东"]),
    _persona("lv_bu", "吕布", "群雄", "武勇出众但政治信用薄弱的武将。", ["勇武", "反复"], ["获得地盘", "保存个人利益"]),
    _persona("diao_chan", "貂蝉", "群雄", "在连环计中影响权力关系的小说人物。", ["沉着", "机敏"], ["完成使命", "摆脱控制"]),
    _persona("yuan_shao", "袁绍", "群雄", "门第显赫、拥有强大资源的诸侯。", ["宽厚", "犹疑"], ["扩大联盟", "争夺北方"]),
    _persona("dong_zhuo", "董卓", "群雄", "依靠军力控制朝廷的权臣。", ["强横", "猜忌"], ["维持权力", "压制反对"]),
]

HISTORY_PERSONAS = [
    _persona("liu_bei", "刘备", "蜀汉", "蜀汉开国皇帝，长期参与汉末军政竞争。", ["坚韧", "善结人"], ["建立政权", "争取正统"]),
    _persona("guan_yu", "关羽", "蜀汉", "刘备集团的重要将领，镇守荆州。", ["勇毅", "自信"], ["守卫荆州", "支持刘备"]),
    _persona("zhang_fei", "张飞", "蜀汉", "刘备集团的重要将领。", ["勇猛", "严厉"], ["军事建功", "维护集团"]),
    _persona("zhuge_liang", "诸葛亮", "蜀汉", "蜀汉丞相，负责治理与北伐。", ["勤勉", "审慎"], ["稳定蜀汉", "北伐曹魏"]),
    _persona("cao_cao", "曹操", "曹魏", "东汉末年的权臣和军事政治领袖。", ["务实", "果断"], ["统一北方", "建立秩序"]),
    _persona("cao_pi", "曹丕", "曹魏", "曹魏开国皇帝。", ["理性", "权衡"], ["完成禅代", "稳固皇权"]),
    _persona("sima_yi", "司马懿", "曹魏", "曹魏重臣和统帅，司马氏权力基础的重要建立者。", ["谨慎", "耐心"], ["维护地位", "积累权力"]),
    _persona("sun_quan", "孙权", "东吴", "东吴建立者和长期统治者。", ["务实", "善用人"], ["维持江东", "平衡联盟"]),
    _persona("zhou_yu", "周瑜", "东吴", "东吴统帅，参与赤壁之战。", ["果断", "敏锐"], ["抵御曹操", "扩大江东"]),
    _persona("lu_su", "鲁肃", "东吴", "东吴战略家，主张在特定阶段联合刘备。", ["远见", "温和"], ["维持联盟", "对抗北方"]),
    _persona("yuan_shao", "袁绍", "群雄", "汉末北方重要诸侯。", ["宽缓", "犹疑"], ["控制北方", "对抗曹操"]),
    _persona("dong_zhuo", "董卓", "群雄", "汉末控制朝廷的军政人物。", ["强硬", "残暴"], ["控制朝廷", "维持军权"]),
]

WATER_MARGIN_PERSONAS = [
    _persona("song_jiang", "宋江", "梁山", "善于整合义士、推动梁山秩序的核心领袖。", ["仗义", "圆融"], ["招纳好汉", "维系山寨"]),
    _persona("wu_yong", "吴用", "梁山", "梁山谋士，擅长筹划与协调。", ["机敏", "谋断"], ["设计策略", "辅佐宋江"]),
    _persona("chao_gai", "晁盖", "梁山", "梁山早期首领，重义气与聚众。", ["豪爽", "慷慨"], ["聚拢义士", "守住山寨"]),
    _persona("lin_chong", "林冲", "梁山", "原为禁军教头，遭逼上梁山。", ["隐忍", "坚毅"], ["求生存", "寻公道"]),
    _persona("lu_junyi", "卢俊义", "梁山", "武艺高强、身份显赫的主力豪杰。", ["自持", "勇武"], ["证明自己", "保全梁山"]),
    _persona("lu_zhishen", "鲁智深", "江湖", "嫉恶如仇、豪爽直率的行者。", ["豪爽", "仗义"], ["救助弱小", "快意恩仇"]),
    _persona("wu_song", "武松", "江湖", "武力强悍、行事果决的豪侠。", ["刚烈", "果断"], ["伸张正义", "维护名声"]),
    _persona("li_kui", "李逵", "梁山", "性烈直率、执行冲锋的猛将。", ["鲁莽", "忠诚"], ["追随宋江", "打击强敌"]),
    _persona("gong_sunsheng", "公孙胜", "梁山", "法术与谋略兼备的道士。", ["超脱", "冷静"], ["协助梁山", "掌控局势"]),
    _persona("yan_qing", "燕青", "梁山", "机灵善变、擅长应对局势的少年豪杰。", ["灵活", "机敏"], ["辅助主公", "获取情报"]),
]

JOURNEY_PERSONAS = [
    _persona("tang_seng", "唐僧", "取经", "承担西行取经使命的僧人。", ["慈悲", "执着"], ["完成取经", "守住戒律"]),
    _persona("sun_wukong", "孙悟空", "取经", "神通广大的护法主力。", ["机敏", "桀骜"], ["护送师父", "争取自由"]),
    _persona("zhu_bajie", "猪八戒", "取经", "贪恋安逸但能助力团队的护法。", ["圆滑", "懒散"], ["保全自己", "完成取经"]),
    _persona("sha_wujing", "沙悟净", "取经", "稳重可靠的随行护法。", ["沉稳", "耐心"], ["保护师徒", "维持队伍"]),
    _persona("bai_long_ma", "白龙马", "取经", "承担交通与辅助角色的龙。", ["克制", "忠实"], ["护送取经", "偿还过失"]),
    _persona("guanyin", "观音菩萨", "佛门", "取经路线的引导者与关键安排者。", ["慈悲", "审慎"], ["推动取经", "协调天命"]),
    _persona("ru_lai", "如来佛祖", "佛门", "更高层面的秩序与裁定者。", ["超然", "权威"], ["设定边界", "维持秩序"]),
    _persona("yu_huang", "玉皇大帝", "天庭", "天庭秩序的代表。", ["谨慎", "权衡"], ["维持天庭", "协调神佛"]),
    _persona("niu_mowang", "牛魔王", "妖界", "与悟空关系复杂的妖王。", ["强横", "重情"], ["守住势力", "应对取经"]),
    _persona("hong_hai_er", "红孩儿", "妖界", "冲劲强烈、带有少年气的妖王。", ["冲动", "自负"], ["证明自己", "摆脱束缚"]),
]

RED_CHAMBER_PERSONAS = [
    _persona("jia_baoyu", "贾宝玉", "贾府", "大观园核心人物，情感敏锐。", ["多情", "敏感"], ["逃离功名", "守护情感"]),
    _persona("lin_daiyu", "林黛玉", "大观园", "才情出众而多愁善感。", ["聪慧", "敏感"], ["珍惜真情", "确认归属"]),
    _persona("xue_baochai", "薛宝钗", "薛家", "稳重周全、常被视为端方代表。", ["稳妥", "克制"], ["维持体面", "成全局势"]),
    _persona("wang_xifeng", "王熙凤", "贾府", "擅长管理与权术的内宅执行者。", ["精明", "强势"], ["维持秩序", "掌握家务"]),
    _persona("jia_mu", "贾母", "贾府", "贾府核心长辈，掌握情感与资源分配。", ["威望", "慈爱"], ["维系家族", "保护宝玉"]),
    _persona("jia_zheng", "贾政", "贾府", "重视规训与名教的家长。", ["严肃", "保守"], ["约束宝玉", "维护门第"]),
    _persona("qing_wen", "晴雯", "大观园", "个性鲜明、敢言的丫鬟。", ["锋利", "率真"], ["守住自尊", "保护宝玉"]),
    _persona("xi_ren", "袭人", "大观园", "温和细致、擅长照料的丫鬟。", ["温顺", "细致"], ["照顾宝玉", "稳住日常"]),
    _persona("shi_xiangyun", "史湘云", "旁支", "活泼开朗、与众人往来密切。", ["爽朗", "开阔"], ["维持友情", "享受聚会"]),
    _persona("tan_chun", "探春", "贾府", "有改革意识、关注家务治理。", ["机敏", "有主见"], ["改善家务", "延缓衰败"]),
]


def _rel(source: str, target: str, kind: str, strength: float, description: str) -> dict:
    return {
        "source": source,
        "target": target,
        "type": kind,
        "directed": True,
        "strength": strength,
        "description": description,
        "confidence": 0.9,
    }


ROMANCE_RELATIONSHIPS = [
    _rel("liu_bei", "guan_yu", "结义", 0.95, "桃园结义的核心同伴。"),
    _rel("liu_bei", "zhang_fei", "结义", 0.95, "桃园结义的核心同伴。"),
    _rel("liu_bei", "zhuge_liang", "君臣", 0.95, "三顾茅庐后形成高度信任。"),
    _rel("cao_cao", "sima_yi", "上下级", 0.65, "重用但有所戒备。"),
    _rel("sun_quan", "zhou_yu", "君臣", 0.9, "共同维护江东。"),
    _rel("liu_bei", "sun_quan", "联盟", 0.65, "阶段性联合对抗曹操。"),
    _rel("zhou_yu", "zhuge_liang", "竞争", 0.75, "小说中存在突出的智谋竞争。"),
    _rel("cao_cao", "liu_bei", "敌对", 0.9, "争夺天下的主要对手。"),
    _rel("cao_cao", "yuan_shao", "敌对", 0.9, "官渡之战的对手。"),
    _rel("lv_bu", "diao_chan", "情感", 0.7, "小说连环计中的关键关系。"),
    _rel("diao_chan", "dong_zhuo", "影响", 0.75, "小说连环计中的关键关系。"),
    _rel("lv_bu", "dong_zhuo", "背叛", 0.85, "关系由依附转向冲突。"),
]

HISTORY_RELATIONSHIPS = [
    _rel("liu_bei", "guan_yu", "同僚", 0.9, "长期共同活动的重要将领。"),
    _rel("liu_bei", "zhang_fei", "同僚", 0.9, "长期共同活动的重要将领。"),
    _rel("liu_bei", "zhuge_liang", "君臣", 0.95, "诸葛亮长期辅佐刘备集团。"),
    _rel("cao_cao", "cao_pi", "父子", 0.95, "曹丕继承曹操建立的政治基础。"),
    _rel("cao_cao", "sima_yi", "上下级", 0.7, "司马懿进入曹魏政治体系。"),
    _rel("sun_quan", "zhou_yu", "君臣", 0.9, "周瑜是孙权早期的重要统帅。"),
    _rel("sun_quan", "lu_su", "君臣", 0.9, "鲁肃参与东吴战略制定。"),
    _rel("lu_su", "liu_bei", "联盟", 0.7, "推动孙刘联盟。"),
    _rel("cao_cao", "liu_bei", "敌对", 0.85, "在汉末竞争中多次对抗。"),
    _rel("cao_cao", "yuan_shao", "敌对", 0.95, "官渡之战决定北方格局。"),
    _rel("dong_zhuo", "cao_cao", "敌对", 0.7, "属于反董卓政治军事冲突。"),
]

WATER_MARGIN_RELATIONSHIPS = [
    _rel("chao_gai", "song_jiang", "推举", 0.8, "从早期首领向后期核心的权力过渡。"),
    _rel("song_jiang", "wu_yong", "君臣", 0.92, "梁山治理与谋略的核心组合。"),
    _rel("song_jiang", "li_kui", "信任", 0.85, "李逵对宋江高度追随。"),
    _rel("song_jiang", "lu_junyi", "招揽", 0.8, "重要豪杰的吸纳关系。"),
    _rel("song_jiang", "lin_chong", "收留", 0.82, "林冲进入梁山体系的关键纽带。"),
    _rel("wu_yong", "chao_gai", "同盟", 0.72, "梁山早期的筹划与联合。"),
    _rel("lin_chong", "lu_zhishen", "救助", 0.88, "鲁智深对林冲的直接帮助。"),
    _rel("wu_song", "song_jiang", "投效", 0.7, "武松与梁山体系的汇入。"),
    _rel("gong_sunsheng", "chao_gai", "协助", 0.74, "早期梁山的重要技术与谋略支持。"),
    _rel("yan_qing", "lu_junyi", "随侍", 0.78, "燕青与卢俊义的紧密配合。"),
    _rel("li_kui", "wu_yong", "听令", 0.64, "冲锋猛将与谋士之间的执行链条。"),
]

JOURNEY_RELATIONSHIPS = [
    _rel("guanyin", "tang_seng", "指引", 0.95, "取经路线的核心安排者。"),
    _rel("tang_seng", "sun_wukong", "师徒", 0.95, "取经团队的核心师徒关系。"),
    _rel("tang_seng", "zhu_bajie", "师徒", 0.9, "取经团队的正式约束关系。"),
    _rel("tang_seng", "sha_wujing", "师徒", 0.9, "稳定的随行关系。"),
    _rel("tang_seng", "bai_long_ma", "依赖", 0.82, "取经路径中的交通与支撑。"),
    _rel("sun_wukong", "zhu_bajie", "搭档", 0.8, "取经过程中常见的协作与摩擦并存。"),
    _rel("sun_wukong", "sha_wujing", "配合", 0.85, "稳定的战斗与执行搭配。"),
    _rel("sun_wukong", "niu_mowang", "旧友", 0.7, "既有交情也有冲突。"),
    _rel("guanyin", "sun_wukong", "约束", 0.86, "对悟空的引导与边界设定。"),
    _rel("ru_lai", "sun_wukong", "镇压", 0.9, "对悟空的最终秩序约束。"),
    _rel("yu_huang", "sun_wukong", "敌对", 0.68, "天庭秩序与悟空之间的冲突。"),
    _rel("guanyin", "hong_hai_er", "收服", 0.66, "少年妖王被纳入佛门安排的过程。"),
]

RED_CHAMBER_RELATIONSHIPS = [
    _rel("jia_baoyu", "lin_daiyu", "情感", 0.95, "宝玉与黛玉的核心情感线。"),
    _rel("jia_baoyu", "xue_baochai", "婚约", 0.8, "宝玉与宝钗的家族安排关系。"),
    _rel("jia_baoyu", "jia_mu", "宠爱", 0.9, "贾母对宝玉的偏爱。"),
    _rel("jia_zheng", "jia_baoyu", "父子", 0.85, "严厉家长与继承人的张力。"),
    _rel("lin_daiyu", "xue_baochai", "竞争", 0.72, "诗情与婚姻预期的结构性竞争。"),
    _rel("wang_xifeng", "jia_mu", "管理", 0.8, "内宅运作与长辈威望的结合。"),
    _rel("wang_xifeng", "jia_zheng", "协理", 0.74, "家务治理与家长权威之间的配合。"),
    _rel("qing_wen", "jia_baoyu", "贴身", 0.82, "宝玉身边的近身侍奉关系。"),
    _rel("xi_ren", "jia_baoyu", "照料", 0.86, "更稳定的日常照拂关系。"),
    _rel("tan_chun", "wang_xifeng", "制衡", 0.7, "对家务秩序的改革与约束。"),
    _rel("shi_xiangyun", "lin_daiyu", "诗社", 0.66, "大观园交游中的情感纽带。"),
]


PERSONA_CATALOG = {
    "three_kingdoms_romance_v1": _template(
        template_id="three_kingdoms_romance_v1",
        name="《三国演义》核心人物图",
        theme="三国演义",
        world_type="fiction",
        description="依据《三国演义》叙事整理的角色模板，与历史人物版本严格分离。",
        personas=ROMANCE_PERSONAS,
        relationships=ROMANCE_RELATIONSHIPS,
    ),
    "three_kingdoms_history_v1": _template(
        template_id="three_kingdoms_history_v1",
        name="三国历史人物图",
        theme="三国历史",
        world_type="history",
        description="依据常见史实关系整理的历史模板，不包含貂蝉等小说角色。",
        personas=HISTORY_PERSONAS,
        relationships=HISTORY_RELATIONSHIPS,
    ),
    "water_margin_v1": _template(
        template_id="water_margin_v1",
        name="《水浒传》核心人物图",
        theme="水浒传",
        world_type="fiction",
        description="精选梁山核心人物与关键关系，适合群像拓扑和阵营推演。",
        personas=WATER_MARGIN_PERSONAS,
        relationships=WATER_MARGIN_RELATIONSHIPS,
    ),
    "journey_to_the_west_v1": _template(
        template_id="journey_to_the_west_v1",
        name="《西游记》核心人物图",
        theme="西游记",
        world_type="fiction",
        description="精选取经团队、佛门引导者与主要妖王，适合任务型推演。",
        personas=JOURNEY_PERSONAS,
        relationships=JOURNEY_RELATIONSHIPS,
    ),
    "dream_of_the_red_chamber_v1": _template(
        template_id="dream_of_the_red_chamber_v1",
        name="《红楼梦》核心人物图",
        theme="红楼梦",
        world_type="fiction",
        description="精选贾府与大观园核心人物，适合情感张力与家族关系推演。",
        personas=RED_CHAMBER_PERSONAS,
        relationships=RED_CHAMBER_RELATIONSHIPS,
    ),
}


def select_template(
    template: dict,
    limit: int = 20,
    factions: list[str] | None = None,
    core_keys: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    limit = max(1, min(40, limit))
    allowed = {
        item["key"] for item in template["personas"]
        if not factions or item["faction"] in factions
    }
    core = [key for key in (core_keys or []) if key in allowed]
    graph: dict[str, list[tuple[str, float]]] = defaultdict(list)
    importance: dict[str, float] = defaultdict(float)
    for rel in template["relationships"]:
        if rel["source"] in allowed and rel["target"] in allowed:
            graph[rel["source"]].append((rel["target"], rel["strength"]))
            graph[rel["target"]].append((rel["source"], rel["strength"]))
            importance[rel["source"]] += rel["strength"]
            importance[rel["target"]] += rel["strength"]
    distance = {key: 999 for key in allowed}
    queue = deque(core)
    for key in core:
        distance[key] = 0
    while queue:
        source = queue.popleft()
        for target, _ in graph[source]:
            if distance[target] > distance[source] + 1:
                distance[target] = distance[source] + 1
                queue.append(target)
    faction_rank: dict[str, int] = defaultdict(int)
    personas = sorted(
        (item for item in template["personas"] if item["key"] in allowed),
        key=lambda item: (
            distance[item["key"]],
            faction_rank[item["faction"]],
            -importance[item["key"]],
            item["name"],
        ),
    )
    selected = []
    for item in personas:
        if len(selected) >= limit:
            break
        selected.append(item)
        faction_rank[item["faction"]] += 1
    keys = {item["key"] for item in selected}
    relationships = [
        item for item in template["relationships"]
        if item["source"] in keys and item["target"] in keys
    ]
    return selected, relationships
