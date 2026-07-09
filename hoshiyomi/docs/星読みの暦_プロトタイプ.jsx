import { useState, useMemo } from "react";

/* ============================================================
   星読みダッシュボード — プロトタイプ
   夜の暦(こよみ)テーマ / 出生図・38日トランジット・AI鑑定
   ============================================================ */

const DATA = {"version":"nanami-products-yaml-v1","meta":{"schema_version":"1.1","product_type":"western_31days_transit_addon","profile_id":"profile_bfd713c3dc78dda7","chart_id":"chart_c36542f98d2d7e71","generated_at":"2026-06-01T00:06:04.218328+00:00","data_role":"base_chart","addon_type":"western_31days_transit","campaign_id":"note-2026-07","target_month":"2026-07"},"birth_time":{"input_value":"20:41","calculation_time":"20:41","accuracy":"exact","note":"出生時刻あり。ハウス・ASC・MCを通常通り使用できます。"},"interpretation_flags":{"allow_house_interpretation":true,"allow_asc_mc_interpretation":true,"house_reliability":"high","moon_reliability":"high"},"input":{"title":"リサフル6/1","birth_date":"1976-08-10","birth_time":"20:41","prefecture":"東京都","birth_place":"東京都","birth_lat":35.6895,"birth_lng":139.6917,"timezone":"Asia/Tokyo"},"systems":{"western":{"natal":{"engine":"Swiss Ephemeris","house_system":"P","bodies":{"Sun":{"sign":"Leo","sign_ja":"獅子座","degree":17.9572,"absolute_longitude":137.9572,"house":5,"retrograde":false},"Moon":{"sign":"Aqu","sign_ja":"水瓶座","degree":23.9421,"absolute_longitude":323.9421,"house":11,"retrograde":false},"Mercury":{"sign":"Vir","sign_ja":"乙女座","degree":10.7232,"absolute_longitude":160.7232,"house":6,"retrograde":false},"Venus":{"sign":"Vir","sign_ja":"乙女座","degree":2.62,"absolute_longitude":152.62,"house":6,"retrograde":false},"Mars":{"sign":"Vir","sign_ja":"乙女座","degree":21.272,"absolute_longitude":171.272,"house":6,"retrograde":false},"Jupiter":{"sign":"Tau","sign_ja":"牡牛座","degree":28.6592,"absolute_longitude":58.6592,"house":2,"retrograde":false},"Saturn":{"sign":"Leo","sign_ja":"獅子座","degree":8.0832,"absolute_longitude":128.0832,"house":5,"retrograde":false},"Uranus":{"sign":"Sco","sign_ja":"蠍座","degree":3.4291,"absolute_longitude":213.4291,"house":7,"retrograde":false},"Neptune":{"sign":"Sag","sign_ja":"射手座","degree":11.2395,"absolute_longitude":251.2395,"house":9,"retrograde":true},"Pluto":{"sign":"Lib","sign_ja":"天秤座","degree":9.6682,"absolute_longitude":189.6682,"house":7,"retrograde":false},"North Node":{"sign":"Sco","sign_ja":"蠍座","degree":6.9178,"absolute_longitude":216.9178,"house":7,"retrograde":true},"South Node":{"sign":"Tau","sign_ja":"牡牛座","degree":6.9178,"absolute_longitude":36.9178,"house":1,"retrograde":true},"ASC":{"sign":"Ari","sign_ja":"牡羊座","degree":6.3569,"absolute_longitude":6.3569,"house":1,"retrograde":false},"MC":{"sign":"Cap","sign_ja":"山羊座","degree":3.6904,"absolute_longitude":273.6904,"house":10,"retrograde":false}},"houses":{"1":{"sign":"Ari","sign_ja":"牡羊座","degree":6.3569},"2":{"sign":"Tau","sign_ja":"牡牛座","degree":14.5097},"3":{"sign":"Gem","sign_ja":"双子座","degree":11.2365},"4":{"sign":"Can","sign_ja":"蟹座","degree":3.6904},"5":{"sign":"Can","sign_ja":"蟹座","degree":26.7076},"6":{"sign":"Leo","sign_ja":"獅子座","degree":25.35},"7":{"sign":"Lib","sign_ja":"天秤座","degree":6.3569},"8":{"sign":"Sco","sign_ja":"蠍座","degree":14.5097},"9":{"sign":"Sag","sign_ja":"射手座","degree":11.2365},"10":{"sign":"Cap","sign_ja":"山羊座","degree":3.6904},"11":{"sign":"Cap","sign_ja":"山羊座","degree":26.7076},"12":{"sign":"Aqu","sign_ja":"水瓶座","degree":25.35}},"aspects":[{"body1":"North Node","body2":"South Node","aspect":"opposition","orb":0.0},{"body1":"Jupiter","body2":"Juno","aspect":"trine","orb":0.04},{"body1":"Pallas","body2":"MC","aspect":"opposition","orb":0.2},{"body1":"Uranus","body2":"MC","aspect":"sextile","orb":0.26},{"body1":"Pluto","body2":"Ceres","aspect":"sextile","orb":0.43},{"body1":"Uranus","body2":"Pallas","aspect":"trine","orb":0.47},{"body1":"Mercury","body2":"Neptune","aspect":"square","orb":0.52},{"body1":"Venus","body2":"Chiron","aspect":"trine","orb":0.72},{"body1":"Mercury","body2":"Lilith","aspect":"trine","orb":0.8},{"body1":"Venus","body2":"Uranus","aspect":"sextile","orb":0.81},{"body1":"MC","body2":"Vertex","aspect":"square","orb":0.96},{"body1":"Venus","body2":"MC","aspect":"trine","orb":1.07},{"body1":"Chiron","body2":"Vesta","aspect":"sextile","orb":1.1},{"body1":"Neptune","body2":"Ceres","aspect":"trine","orb":1.14},{"body1":"Pallas","body2":"Vertex","aspect":"square","orb":1.16},{"body1":"Saturn","body2":"North Node","aspect":"square","orb":1.17},{"body1":"Saturn","body2":"South Node","aspect":"square","orb":1.17},{"body1":"Venus","body2":"Pallas","aspect":"sextile","orb":1.28},{"body1":"Lilith","body2":"Ceres","aspect":"square","orb":1.43},{"body1":"Uranus","body2":"Chiron","aspect":"opposition","orb":1.53},{"body1":"Neptune","body2":"Pluto","aspect":"sextile","orb":1.57},{"body1":"Saturn","body2":"Pluto","aspect":"sextile","orb":1.59},{"body1":"Saturn","body2":"ASC","aspect":"trine","orb":1.73},{"body1":"Chiron","body2":"MC","aspect":"trine","orb":1.79},{"body1":"Venus","body2":"Vesta","aspect":"sextile","orb":1.82},{"body1":"Saturn","body2":"Ceres","aspect":"conjunction","orb":2.01},{"body1":"Saturn","body2":"Neptune","aspect":"trine","orb":3.16},{"body1":"Pluto","body2":"ASC","aspect":"opposition","orb":3.31},{"body1":"Uranus","body2":"North Node","aspect":"conjunction","orb":3.49},{"body1":"Mercury","body2":"North Node","aspect":"sextile","orb":3.81},{"body1":"Venus","body2":"Jupiter","aspect":"square","orb":3.96},{"body1":"Saturn","body2":"Uranus","aspect":"square","orb":4.65},{"body1":"Moon","body2":"Jupiter","aspect":"square","orb":4.72},{"body1":"Neptune","body2":"ASC","aspect":"trine","orb":4.88},{"body1":"Sun","body2":"Moon","aspect":"opposition","orb":5.98},{"body1":"Mars","body2":"Juno","aspect":"conjunction","orb":7.43},{"body1":"Sun","body2":"Ceres","aspect":"conjunction","orb":7.86}],"summary":{"elements":{"fire":3,"earth":4,"air":2,"water":1},"modes":{"cardinal":1,"fixed":5,"mutable":4},"dominant_signs":[{"sign":"Vir","sign_ja":"乙女座","count":3},{"sign":"Leo","sign_ja":"獅子座","count":2},{"sign":"Aqu","sign_ja":"水瓶座","count":1}]}},"asteroids":{"Lilith":{"sign":"Tau","sign_ja":"牡牛座","degree":11.5232,"house":1,"retrograde":true},"Chiron":{"sign":"Tau","sign_ja":"牡牛座","degree":1.9028,"house":1,"retrograde":true},"Ceres":{"sign":"Leo","sign_ja":"獅子座","degree":10.0952,"house":5,"retrograde":false},"Pallas":{"sign":"Can","sign_ja":"蟹座","degree":3.8953,"house":4,"retrograde":false},"Juno":{"sign":"Vir","sign_ja":"乙女座","degree":28.7017,"house":6,"retrograde":false},"Vesta":{"sign":"Can","sign_ja":"蟹座","degree":0.8015,"house":3,"retrograde":false},"Vertex":{"sign":"Lib","sign_ja":"天秤座","degree":2.7331,"house":6,"retrograde":false}},"transit":{"period":{"start_date":"2026-07-01","days":38,"timezone":"Asia/Tokyo","end_date":"2026-08-07"},"daily":[{"date":"2026-07-01","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":9.322,"house":9,"retrograde":false},"Moon":{"sign_ja":"山羊座","degree":21.7151,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":26.1831,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":20.3348,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":1.6474,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":0.1884,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.1921,"house":7,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.7138,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4071,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.8734,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Pluto","aspect":"square","orb":0.35},{"transit_body":"Moon","natal_body":"Mars","aspect":"trine","orb":0.44},{"transit_body":"Mars","natal_body":"Venus","aspect":"square","orb":0.97},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.09},{"transit_body":"Sun","natal_body":"Mercury","aspect":"sextile","orb":1.4},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.44}],"moon_timepoints":[{"label":"morning","sign_ja":"山羊座","degree":18.721,"house":6,"aspects":[]},{"label":"noon","sign_ja":"山羊座","degree":21.7151,"house":4,"aspects":[{"natal_body":"Mars","aspect":"trine","orb":0.44}]},{"label":"night","sign_ja":"山羊座","degree":26.2158,"house":12,"aspects":[]}]},{"date":"2026-07-02","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":10.2752,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":3.7464,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":26.039,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":21.4673,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":2.3579,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":0.4029,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.2341,"house":7,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.7635,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4103,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.8528,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Venus","aspect":"square","orb":0.26},{"transit_body":"Moon","natal_body":"Uranus","aspect":"square","orb":0.32},{"transit_body":"Sun","natal_body":"Mercury","aspect":"sextile","orb":0.45},{"transit_body":"Sun","natal_body":"Pluto","aspect":"square","orb":0.61},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.14},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.42}],"moon_timepoints":[{"label":"morning","sign_ja":"水瓶座","degree":0.7293,"house":7,"aspects":[]},{"label":"noon","sign_ja":"水瓶座","degree":3.7464,"house":4,"aspects":[{"natal_body":"Uranus","aspect":"square","orb":0.32}]},{"label":"night","sign_ja":"水瓶座","degree":8.2854,"house":12,"aspects":[{"natal_body":"Saturn","aspect":"opposition","orb":0.2}]}]},{"date":"2026-07-03","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":11.2285,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":15.8911,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":25.821,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":22.5977,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":3.0673,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":0.6179,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.2746,"house":7,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.8128,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.413,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.8319,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Venus","aspect":"square","orb":0.45},{"transit_body":"Sun","natal_body":"Mercury","aspect":"sextile","orb":0.51},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.19},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.4}],"moon_timepoints":[{"label":"morning","sign_ja":"水瓶座","degree":12.8422,"house":7,"aspects":[]},{"label":"noon","sign_ja":"水瓶座","degree":15.8911,"house":4,"aspects":[]},{"label":"night","sign_ja":"水瓶座","degree":20.4825,"house":1,"aspects":[]}]},{"date":"2026-07-04","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":12.1817,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":28.1891,"house":5,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":25.5317,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":23.7259,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":3.7757,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":0.8334,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.3135,"house":7,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.8617,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4151,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.8108,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Venus","natal_body":"Moon","aspect":"opposition","orb":0.22},{"transit_body":"Moon","natal_body":"Jupiter","aspect":"square","orb":0.47},{"transit_body":"Mars","natal_body":"Venus","aspect":"square","orb":1.16},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.24},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.38},{"transit_body":"Sun","natal_body":"Mercury","aspect":"sextile","orb":1.46}],"moon_timepoints":[{"label":"morning","sign_ja":"水瓶座","degree":25.0977,"house":8,"aspects":[{"natal_body":"Moon","aspect":"conjunction","orb":1.16}]},{"label":"noon","sign_ja":"水瓶座","degree":28.1891,"house":5,"aspects":[{"natal_body":"Jupiter","aspect":"square","orb":0.47}]},{"label":"night","sign_ja":"魚座","degree":2.85,"house":1,"aspects":[{"natal_body":"Venus","aspect":"opposition","orb":0.23},{"natal_body":"Uranus","aspect":"trine","orb":0.58}]}]},{"date":"2026-07-05","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":13.135,"house":9,"retrograde":false},"Moon":{"sign_ja":"魚座","degree":10.6886,"house":5,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":25.1748,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":24.8519,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":4.483,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":1.0494,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.3507,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.9101,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4166,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.7896,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Mercury","aspect":"opposition","orb":0.03},{"transit_body":"Moon","natal_body":"Neptune","aspect":"square","orb":0.55},{"transit_body":"Venus","natal_body":"Moon","aspect":"opposition","orb":0.91},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.29},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.36}],"moon_timepoints":[{"label":"morning","sign_ja":"魚座","degree":7.542,"house":8,"aspects":[]},{"label":"noon","sign_ja":"魚座","degree":10.6886,"house":5,"aspects":[{"natal_body":"Mercury","aspect":"opposition","orb":0.03},{"natal_body":"Neptune","aspect":"square","orb":0.55}]},{"label":"night","sign_ja":"魚座","degree":15.4389,"house":1,"aspects":[]}]},{"date":"2026-07-06","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":14.0883,"house":9,"retrograde":false},"Moon":{"sign_ja":"魚座","degree":23.4441,"house":6,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":24.7549,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":25.9755,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":5.1893,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":1.2658,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.3863,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":3.9581,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4176,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.7681,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.34},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.34}],"moon_timepoints":[{"label":"morning","sign_ja":"魚座","degree":20.2281,"house":9,"aspects":[{"natal_body":"Mars","aspect":"opposition","orb":1.04}]},{"label":"noon","sign_ja":"魚座","degree":23.4441,"house":6,"aspects":[]},{"label":"night","sign_ja":"魚座","degree":28.3051,"house":1,"aspects":[{"natal_body":"Jupiter","aspect":"sextile","orb":0.35}]}]},{"date":"2026-07-07","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":15.0417,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡羊座","degree":6.5125,"house":6,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":24.2777,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":27.0969,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":5.8945,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":1.4826,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.4204,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.0056,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.418,"house":6,"retrograde":false},"Pluto":{"sign_ja":"水瓶座","degree":4.7465,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.32},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.39}],"moon_timepoints":[{"label":"morning","sign_ja":"牡羊座","degree":3.213,"house":9,"aspects":[]},{"label":"noon","sign_ja":"牡羊座","degree":6.5125,"house":6,"aspects":[]},{"label":"night","sign_ja":"牡羊座","degree":11.5047,"house":2,"aspects":[{"natal_body":"Neptune","aspect":"trine","orb":0.27}]}]},{"date":"2026-07-08","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":15.9952,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡羊座","degree":19.9458,"house":7,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":23.75,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":28.2159,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":6.5986,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":1.6999,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.4528,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.0526,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4179,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.7246,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Venus","natal_body":"Jupiter","aspect":"square","orb":0.44},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.3},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.43}],"moon_timepoints":[{"label":"morning","sign_ja":"牡羊座","degree":16.5508,"house":9,"aspects":[]},{"label":"noon","sign_ja":"牡羊座","degree":19.9458,"house":7,"aspects":[]},{"label":"night","sign_ja":"牡羊座","degree":25.0856,"house":2,"aspects":[{"natal_body":"Moon","aspect":"sextile","orb":1.14}]}]},{"date":"2026-07-09","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":16.9489,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡牛座","degree":3.7807,"house":7,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":23.1797,"house":10,"retrograde":true},"Venus":{"sign_ja":"獅子座","degree":29.3326,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":7.3017,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":1.9176,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.4835,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.0991,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4173,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.7027,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Uranus","aspect":"opposition","orb":0.35},{"transit_body":"Venus","natal_body":"Jupiter","aspect":"square","orb":0.67},{"transit_body":"Mars","natal_body":"Saturn","aspect":"sextile","orb":0.78},{"transit_body":"Moon","natal_body":"Venus","aspect":"trine","orb":1.16},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.27},{"transit_body":"Uranus","natal_body":"Venus","aspect":"square","orb":1.48}],"moon_timepoints":[{"label":"morning","sign_ja":"牡牛座","degree":0.2832,"house":10,"aspects":[]},{"label":"noon","sign_ja":"牡牛座","degree":3.7807,"house":7,"aspects":[{"natal_body":"Uranus","aspect":"opposition","orb":0.35},{"natal_body":"Venus","aspect":"trine","orb":1.16}]},{"label":"night","sign_ja":"牡牛座","degree":9.0752,"house":2,"aspects":[{"natal_body":"Saturn","aspect":"square","orb":0.99}]}]},{"date":"2026-07-10","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":17.9026,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡牛座","degree":18.0257,"house":8,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":22.5756,"house":10,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":0.4469,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":8.0037,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":2.1357,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.5127,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.1452,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4162,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.6806,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Sun","aspect":"square","orb":0.07},{"transit_body":"Mars","natal_body":"Saturn","aspect":"sextile","orb":0.08},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.25},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":1.29}],"moon_timepoints":[{"label":"morning","sign_ja":"牡牛座","degree":14.4269,"house":10,"aspects":[]},{"label":"noon","sign_ja":"牡牛座","degree":18.0257,"house":8,"aspects":[{"natal_body":"Sun","aspect":"square","orb":0.07}]},{"label":"night","sign_ja":"牡牛座","degree":23.4682,"house":3,"aspects":[{"natal_body":"Moon","aspect":"square","orb":0.47}]}]},{"date":"2026-07-11","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":18.8565,"house":9,"retrograde":false},"Moon":{"sign_ja":"双子座","degree":2.6487,"house":8,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":21.9473,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":1.5587,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":8.7046,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":2.3542,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.5402,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.1907,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4145,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.6583,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Venus","aspect":"square","orb":0.03},{"transit_body":"Mars","natal_body":"Saturn","aspect":"sextile","orb":0.62},{"transit_body":"Mercury","natal_body":"Mars","aspect":"sextile","orb":0.68},{"transit_body":"Mars","natal_body":"Pluto","aspect":"trine","orb":0.96},{"transit_body":"Venus","natal_body":"Venus","aspect":"conjunction","orb":1.06},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":1.07},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.23}],"moon_timepoints":[{"label":"morning","sign_ja":"牡牛座","degree":28.961,"house":10,"aspects":[{"natal_body":"Jupiter","aspect":"conjunction","orb":0.3}]},{"label":"noon","sign_ja":"双子座","degree":2.6487,"house":8,"aspects":[{"natal_body":"Venus","aspect":"square","orb":0.03}]},{"label":"night","sign_ja":"双子座","degree":8.215,"house":3,"aspects":[{"natal_body":"Saturn","aspect":"sextile","orb":0.13}]}]},{"date":"2026-07-12","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":19.8106,"house":9,"retrograde":false},"Moon":{"sign_ja":"双子座","degree":17.5697,"house":8,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":21.3052,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":2.6679,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":9.4044,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":2.5731,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.566,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.2358,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4123,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.636,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mercury","natal_body":"Mars","aspect":"sextile","orb":0.03},{"transit_body":"Venus","natal_body":"Venus","aspect":"conjunction","orb":0.05},{"transit_body":"Mars","natal_body":"Pluto","aspect":"trine","orb":0.26},{"transit_body":"Moon","natal_body":"Sun","aspect":"sextile","orb":0.39},{"transit_body":"Venus","natal_body":"Uranus","aspect":"sextile","orb":0.76},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.86},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.21},{"transit_body":"Sun","natal_body":"Mars","aspect":"sextile","orb":1.46}],"moon_timepoints":[{"label":"morning","sign_ja":"双子座","degree":13.8177,"house":11,"aspects":[]},{"label":"noon","sign_ja":"双子座","degree":17.5697,"house":8,"aspects":[{"natal_body":"Sun","aspect":"sextile","orb":0.39}]},{"label":"night","sign_ja":"双子座","degree":23.2174,"house":4,"aspects":[{"natal_body":"Moon","aspect":"trine","orb":0.72}]}]},{"date":"2026-07-13","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":20.7647,"house":9,"retrograde":false},"Moon":{"sign_ja":"蟹座","degree":2.6627,"house":9,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":20.6602,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":3.7747,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":10.1031,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":2.7923,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.5902,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.2804,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4096,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.6135,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Venus","aspect":"sextile","orb":0.04},{"transit_body":"Venus","natal_body":"Uranus","aspect":"sextile","orb":0.35},{"transit_body":"Mars","natal_body":"Pluto","aspect":"trine","orb":0.43},{"transit_body":"Sun","natal_body":"Mars","aspect":"sextile","orb":0.51},{"transit_body":"Mercury","natal_body":"Mars","aspect":"sextile","orb":0.61},{"transit_body":"Mars","natal_body":"Mercury","aspect":"square","orb":0.62},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.64},{"transit_body":"Moon","natal_body":"Uranus","aspect":"trine","orb":0.77},{"transit_body":"Mars","natal_body":"Neptune","aspect":"opposition","orb":1.14},{"transit_body":"Venus","natal_body":"Venus","aspect":"conjunction","orb":1.15},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.18}],"moon_timepoints":[{"label":"morning","sign_ja":"双子座","degree":28.8816,"house":11,"aspects":[]},{"label":"noon","sign_ja":"蟹座","degree":2.6627,"house":9,"aspects":[{"natal_body":"Venus","aspect":"sextile","orb":0.04},{"natal_body":"Uranus","aspect":"trine","orb":0.77}]},{"label":"night","sign_ja":"蟹座","degree":8.3355,"house":5,"aspects":[]}]},{"date":"2026-07-14","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":21.719,"house":9,"retrograde":false},"Moon":{"sign_ja":"蟹座","degree":17.7713,"house":9,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":20.0233,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":4.8787,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":10.8007,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":3.0118,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6127,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.3244,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4063,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.5909,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Mercury","aspect":"square","orb":0.08},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.42},{"transit_body":"Mars","natal_body":"Neptune","aspect":"opposition","orb":0.44},{"transit_body":"Sun","natal_body":"Mars","aspect":"sextile","orb":0.45},{"transit_body":"Mars","natal_body":"Pluto","aspect":"trine","orb":1.13},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.16}],"moon_timepoints":[{"label":"morning","sign_ja":"蟹座","degree":14.0017,"house":12,"aspects":[]},{"label":"noon","sign_ja":"蟹座","degree":17.7713,"house":9,"aspects":[]},{"label":"night","sign_ja":"蟹座","degree":23.4075,"house":5,"aspects":[]}]},{"date":"2026-07-15","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":22.6733,"house":9,"retrograde":false},"Moon":{"sign_ja":"獅子座","degree":2.7332,"house":10,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":19.4058,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":5.98,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":11.4971,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":3.2315,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6335,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.3678,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.4025,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.5682,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.2},{"transit_body":"Mars","natal_body":"Neptune","aspect":"opposition","orb":0.26},{"transit_body":"Moon","natal_body":"Uranus","aspect":"square","orb":0.7},{"transit_body":"Mars","natal_body":"Mercury","aspect":"square","orb":0.77},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.14},{"transit_body":"Sun","natal_body":"Mars","aspect":"sextile","orb":1.4}],"moon_timepoints":[{"label":"morning","sign_ja":"蟹座","degree":29.0148,"house":12,"aspects":[{"natal_body":"Jupiter","aspect":"sextile","orb":0.36}]},{"label":"noon","sign_ja":"獅子座","degree":2.7332,"house":10,"aspects":[{"natal_body":"Uranus","aspect":"square","orb":0.7}]},{"label":"night","sign_ja":"獅子座","degree":8.2761,"house":6,"aspects":[{"natal_body":"Saturn","aspect":"conjunction","orb":0.19}]}]},{"date":"2026-07-16","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":23.6277,"house":9,"retrograde":false},"Moon":{"sign_ja":"獅子座","degree":17.407,"house":10,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":18.8185,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":7.0784,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":12.1922,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":3.4515,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6526,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.4107,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3981,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.5453,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.02},{"transit_body":"Moon","natal_body":"Sun","aspect":"conjunction","orb":0.55},{"transit_body":"Mars","natal_body":"Neptune","aspect":"opposition","orb":0.95},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.12}],"moon_timepoints":[{"label":"morning","sign_ja":"獅子座","degree":13.7719,"house":1,"aspects":[]},{"label":"noon","sign_ja":"獅子座","degree":17.407,"house":10,"aspects":[{"natal_body":"Sun","aspect":"conjunction","orb":0.55}]},{"label":"night","sign_ja":"獅子座","degree":22.8134,"house":6,"aspects":[{"natal_body":"Moon","aspect":"opposition","orb":1.13}]}]},{"date":"2026-07-17","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":24.5821,"house":9,"retrograde":false},"Moon":{"sign_ja":"乙女座","degree":1.6921,"house":11,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":18.272,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":8.1739,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":12.8862,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":3.6717,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6699,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.453,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3932,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.5224,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.24},{"transit_body":"Moon","natal_body":"Venus","aspect":"conjunction","orb":0.93},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.09}],"moon_timepoints":[{"label":"morning","sign_ja":"獅子座","degree":28.161,"house":1,"aspects":[{"natal_body":"Jupiter","aspect":"square","orb":0.5}]},{"label":"noon","sign_ja":"乙女座","degree":1.6921,"house":11,"aspects":[{"natal_body":"Venus","aspect":"conjunction","orb":0.93}]},{"label":"night","sign_ja":"乙女座","degree":6.9367,"house":7,"aspects":[]}]},{"date":"2026-07-18","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":25.5365,"house":9,"retrograde":false},"Moon":{"sign_ja":"乙女座","degree":15.5366,"house":11,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":17.7763,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":9.2664,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":13.579,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":3.8921,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6856,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.4947,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3877,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.4993,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.46},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.07}],"moon_timepoints":[{"label":"morning","sign_ja":"乙女座","degree":12.1178,"house":2,"aspects":[{"natal_body":"Neptune","aspect":"square","orb":0.88}]},{"label":"noon","sign_ja":"乙女座","degree":15.5366,"house":11,"aspects":[]},{"label":"night","sign_ja":"乙女座","degree":20.6122,"house":7,"aspects":[{"natal_body":"Mars","aspect":"conjunction","orb":0.66}]}]},{"date":"2026-07-19","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":26.491,"house":9,"retrograde":false},"Moon":{"sign_ja":"乙女座","degree":28.9344,"house":11,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":17.3406,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":10.3558,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":14.2706,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":4.1127,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6995,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.5358,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3817,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.4762,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Moon","natal_body":"Jupiter","aspect":"trine","orb":0.28},{"transit_body":"Venus","natal_body":"Mercury","aspect":"conjunction","orb":0.37},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.68},{"transit_body":"Venus","natal_body":"Neptune","aspect":"square","orb":0.88},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.05}],"moon_timepoints":[{"label":"morning","sign_ja":"乙女座","degree":25.6257,"house":2,"aspects":[]},{"label":"noon","sign_ja":"乙女座","degree":28.9344,"house":11,"aspects":[{"natal_body":"Jupiter","aspect":"trine","orb":0.28}]},{"label":"night","sign_ja":"天秤座","degree":3.8487,"house":7,"aspects":[]}]},{"date":"2026-07-20","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":27.4456,"house":9,"retrograde":false},"Moon":{"sign_ja":"天秤座","degree":11.9158,"house":12,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.9732,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":11.4419,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":14.961,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":4.3335,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7118,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.5763,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3751,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.4529,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Venus","natal_body":"Neptune","aspect":"square","orb":0.2},{"transit_body":"Moon","natal_body":"Neptune","aspect":"sextile","orb":0.68},{"transit_body":"Venus","natal_body":"Mercury","aspect":"conjunction","orb":0.72},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":0.9},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.02},{"transit_body":"Sun","natal_body":"Jupiter","aspect":"sextile","orb":1.21}],"moon_timepoints":[{"label":"morning","sign_ja":"天秤座","degree":8.7068,"house":3,"aspects":[{"natal_body":"Saturn","aspect":"sextile","orb":0.62},{"natal_body":"Pluto","aspect":"conjunction","orb":0.96}]},{"label":"noon","sign_ja":"天秤座","degree":11.9158,"house":12,"aspects":[{"natal_body":"Neptune","aspect":"sextile","orb":0.68}]},{"label":"night","sign_ja":"天秤座","degree":16.6872,"house":7,"aspects":[]}]},{"date":"2026-07-21","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":28.4002,"house":9,"retrograde":false},"Moon":{"sign_ja":"天秤座","degree":24.5359,"house":12,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.6814,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":12.5247,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":15.6502,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":4.5544,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7223,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.6162,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3681,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.4297,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Jupiter","aspect":"sextile","orb":0.26},{"transit_body":"Moon","natal_body":"Moon","aspect":"trine","orb":0.59},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":1.0},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":1.13}],"moon_timepoints":[{"label":"morning","sign_ja":"天秤座","degree":21.4111,"house":3,"aspects":[]},{"label":"noon","sign_ja":"天秤座","degree":24.5359,"house":12,"aspects":[{"natal_body":"Moon","aspect":"trine","orb":0.59}]},{"label":"night","sign_ja":"天秤座","degree":29.189,"house":8,"aspects":[]}]},{"date":"2026-07-22","transiting_bodies":{"Sun":{"sign_ja":"蟹座","degree":29.3548,"house":9,"retrograde":false},"Moon":{"sign_ja":"蠍座","degree":6.8634,"house":1,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.4716,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":13.6042,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":16.3382,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":4.7754,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7311,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.6555,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3605,"house":6,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.4064,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Jupiter","aspect":"sextile","orb":0.7},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.98},{"transit_body":"Jupiter","natal_body":"Uranus","aspect":"square","orb":1.35}],"moon_timepoints":[{"label":"morning","sign_ja":"蠍座","degree":3.8049,"house":3,"aspects":[{"natal_body":"Uranus","aspect":"conjunction","orb":0.38},{"natal_body":"Venus","aspect":"sextile","orb":1.18}]},{"label":"noon","sign_ja":"蠍座","degree":6.8634,"house":1,"aspects":[]},{"label":"night","sign_ja":"蠍座","degree":11.4258,"house":8,"aspects":[{"natal_body":"Mercury","aspect":"sextile","orb":0.7}]}]},{"date":"2026-07-23","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":0.3096,"house":9,"retrograde":false},"Moon":{"sign_ja":"蠍座","degree":18.9722,"house":1,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.3489,"house":9,"retrograde":true},"Venus":{"sign_ja":"乙女座","degree":14.6801,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":17.025,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":4.9966,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7383,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.6942,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3525,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.383,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Sun","aspect":"sextile","orb":0.93},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.95},{"transit_body":"Moon","natal_body":"Sun","aspect":"square","orb":1.01}],"moon_timepoints":[{"label":"morning","sign_ja":"蠍座","degree":15.9615,"house":4,"aspects":[]},{"label":"noon","sign_ja":"蠍座","degree":18.9722,"house":1,"aspects":[{"natal_body":"Sun","aspect":"square","orb":1.01}]},{"label":"night","sign_ja":"蠍座","degree":23.4717,"house":8,"aspects":[{"natal_body":"Moon","aspect":"square","orb":0.47}]}]},{"date":"2026-07-24","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":1.2644,"house":9,"retrograde":false},"Moon":{"sign_ja":"射手座","degree":0.9351,"house":2,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.3179,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":15.7525,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":17.7106,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":5.2179,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7437,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.7323,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3439,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.3597,"house":4,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Sun","aspect":"sextile","orb":0.25},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.93}],"moon_timepoints":[{"label":"morning","sign_ja":"蠍座","degree":27.9543,"house":4,"aspects":[{"natal_body":"Jupiter","aspect":"opposition","orb":0.7}]},{"label":"noon","sign_ja":"射手座","degree":0.9351,"house":2,"aspects":[]},{"label":"night","sign_ja":"射手座","degree":5.3975,"house":9,"aspects":[]}]},{"date":"2026-07-25","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":2.2194,"house":9,"retrograde":false},"Moon":{"sign_ja":"射手座","degree":12.8193,"house":2,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.3818,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":16.8211,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":18.3951,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":5.4393,"house":10,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7475,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.7698,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3348,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.3363,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Sun","aspect":"sextile","orb":0.44},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.91},{"transit_body":"Sun","natal_body":"Uranus","aspect":"square","orb":1.21}],"moon_timepoints":[{"label":"morning","sign_ja":"射手座","degree":9.8523,"house":4,"aspects":[{"natal_body":"Pluto","aspect":"sextile","orb":0.18},{"natal_body":"Mercury","aspect":"square","orb":0.87}]},{"label":"noon","sign_ja":"射手座","degree":12.8193,"house":2,"aspects":[]},{"label":"night","sign_ja":"射手座","degree":17.268,"house":9,"aspects":[{"natal_body":"Sun","aspect":"trine","orb":0.69}]}]},{"date":"2026-07-26","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":3.1745,"house":9,"retrograde":false},"Moon":{"sign_ja":"射手座","degree":24.6841,"house":2,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.5433,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":17.886,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":19.0784,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":5.6607,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7495,"house":6,"retrograde":false},"Uranus":{"sign_ja":"双子座","degree":4.8066,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3253,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.3129,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Uranus","aspect":"square","orb":0.25},{"transit_body":"Moon","natal_body":"Moon","aspect":"sextile","orb":0.74},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.88},{"transit_body":"Mars","natal_body":"Sun","aspect":"sextile","orb":1.12}],"moon_timepoints":[{"label":"morning","sign_ja":"射手座","degree":21.7168,"house":5,"aspects":[{"natal_body":"Mars","aspect":"square","orb":0.44}]},{"label":"noon","sign_ja":"射手座","degree":24.6841,"house":2,"aspects":[{"natal_body":"Moon","aspect":"sextile","orb":0.74}]},{"label":"night","sign_ja":"射手座","degree":29.139,"house":10,"aspects":[]}]},{"date":"2026-07-27","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":4.1297,"house":9,"retrograde":false},"Moon":{"sign_ja":"山羊座","degree":6.5799,"house":3,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":16.8042,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":18.9469,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":19.7604,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":5.8822,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7499,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":4.8428,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3152,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.2895,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Uranus","aspect":"square","orb":0.7},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.86}],"moon_timepoints":[{"label":"morning","sign_ja":"山羊座","degree":3.6006,"house":5,"aspects":[{"natal_body":"Uranus","aspect":"sextile","orb":0.17},{"natal_body":"Venus","aspect":"trine","orb":0.98}]},{"label":"noon","sign_ja":"山羊座","degree":6.5799,"house":3,"aspects":[]},{"label":"night","sign_ja":"山羊座","degree":11.0575,"house":10,"aspects":[{"natal_body":"Mercury","aspect":"trine","orb":0.33}]}]},{"date":"2026-07-28","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":5.0851,"house":9,"retrograde":false},"Moon":{"sign_ja":"山羊座","degree":18.5481,"house":3,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":17.1657,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":20.0038,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":20.4413,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":6.1037,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7485,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":4.8783,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.3047,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.2661,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Mars","aspect":"square","orb":0.83},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.84}],"moon_timepoints":[{"label":"morning","sign_ja":"山羊座","degree":15.5473,"house":5,"aspects":[]},{"label":"noon","sign_ja":"山羊座","degree":18.5481,"house":3,"aspects":[]},{"label":"night","sign_ja":"山羊座","degree":23.0619,"house":11,"aspects":[]}]},{"date":"2026-07-29","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":6.0407,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":0.6224,"house":3,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":17.6283,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":21.0566,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":21.121,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":6.3252,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7455,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":4.9132,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2936,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.2427,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Mars","aspect":"square","orb":0.15},{"transit_body":"Venus","natal_body":"Mars","aspect":"conjunction","orb":0.22},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.81}],"moon_timepoints":[{"label":"morning","sign_ja":"山羊座","degree":27.5923,"house":6,"aspects":[{"natal_body":"Jupiter","aspect":"trine","orb":1.07}]},{"label":"noon","sign_ja":"水瓶座","degree":0.6224,"house":3,"aspects":[]},{"label":"night","sign_ja":"水瓶座","degree":5.1834,"house":11,"aspects":[]}]},{"date":"2026-07-30","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":6.9964,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":12.8305,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":18.1921,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":22.1051,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":21.7995,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":6.5465,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7407,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":4.9474,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2821,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.2193,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Mars","aspect":"square","orb":0.53},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.79},{"transit_body":"Venus","natal_body":"Mars","aspect":"conjunction","orb":0.83},{"transit_body":"Sun","natal_body":"Saturn","aspect":"conjunction","orb":1.09}],"moon_timepoints":[{"label":"morning","sign_ja":"水瓶座","degree":9.7645,"house":6,"aspects":[{"natal_body":"Pluto","aspect":"trine","orb":0.1}]},{"label":"noon","sign_ja":"水瓶座","degree":12.8305,"house":4,"aspects":[]},{"label":"night","sign_ja":"水瓶座","degree":17.448,"house":11,"aspects":[{"natal_body":"Sun","aspect":"opposition","orb":0.51}]}]},{"date":"2026-07-31","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":7.9524,"house":9,"retrograde":false},"Moon":{"sign_ja":"水瓶座","degree":25.1966,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":18.8567,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":23.1493,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":22.4768,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":6.7679,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7342,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":4.9809,"house":8,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2701,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.1959,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Sun","natal_body":"Saturn","aspect":"conjunction","orb":0.13},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.77},{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":1.32}],"moon_timepoints":[{"label":"morning","sign_ja":"水瓶座","degree":22.089,"house":7,"aspects":[]},{"label":"noon","sign_ja":"水瓶座","degree":25.1966,"house":4,"aspects":[]},{"label":"night","sign_ja":"水瓶座","degree":29.8794,"house":12,"aspects":[]}]},{"date":"2026-08-01","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":8.9086,"house":9,"retrograde":false},"Moon":{"sign_ja":"魚座","degree":7.7439,"house":4,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":19.6214,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":24.189,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":23.1529,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":6.9893,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.726,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.0137,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2575,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.1725,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.74},{"transit_body":"Sun","natal_body":"Pluto","aspect":"sextile","orb":0.76},{"transit_body":"Mars","natal_body":"Moon","aspect":"trine","orb":0.79},{"transit_body":"Sun","natal_body":"Saturn","aspect":"conjunction","orb":0.83},{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":1.09}],"moon_timepoints":[{"label":"morning","sign_ja":"魚座","degree":4.5888,"house":7,"aspects":[{"natal_body":"Uranus","aspect":"trine","orb":1.16}]},{"label":"noon","sign_ja":"魚座","degree":7.7439,"house":4,"aspects":[]},{"label":"night","sign_ja":"魚座","degree":12.5007,"house":12,"aspects":[]}]},{"date":"2026-08-02","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":9.865,"house":9,"retrograde":false},"Moon":{"sign_ja":"魚座","degree":20.4962,"house":5,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":20.4849,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":25.2242,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":23.8279,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":7.2107,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7161,"house":6,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.0458,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2445,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.1492,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mars","natal_body":"Moon","aspect":"trine","orb":0.11},{"transit_body":"Sun","natal_body":"Pluto","aspect":"sextile","orb":0.2},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.72},{"transit_body":"Moon","natal_body":"Mars","aspect":"opposition","orb":0.78},{"transit_body":"Mercury","natal_body":"Mars","aspect":"sextile","orb":0.79},{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.87},{"transit_body":"Sun","natal_body":"Neptune","aspect":"trine","orb":1.37}],"moon_timepoints":[{"label":"morning","sign_ja":"魚座","degree":17.2875,"house":8,"aspects":[]},{"label":"noon","sign_ja":"魚座","degree":20.4962,"house":5,"aspects":[{"natal_body":"Mars","aspect":"opposition","orb":0.78}]},{"label":"night","sign_ja":"魚座","degree":25.3362,"house":12,"aspects":[]}]},{"date":"2026-08-03","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":10.8218,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡羊座","degree":3.4786,"house":5,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":21.446,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":26.2546,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":24.5016,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":7.4319,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.7045,"house":5,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.0772,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.231,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.1259,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Mercury","natal_body":"Mars","aspect":"sextile","orb":0.17},{"transit_body":"Sun","natal_body":"Neptune","aspect":"trine","orb":0.42},{"transit_body":"Mars","natal_body":"Moon","aspect":"trine","orb":0.56},{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.65},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.7},{"transit_body":"Sun","natal_body":"Pluto","aspect":"sextile","orb":1.15}],"moon_timepoints":[{"label":"morning","sign_ja":"牡羊座","degree":0.21,"house":8,"aspects":[]},{"label":"noon","sign_ja":"牡羊座","degree":3.4786,"house":5,"aspects":[]},{"label":"night","sign_ja":"牡羊座","degree":8.4116,"house":1,"aspects":[{"natal_body":"Saturn","aspect":"trine","orb":0.33}]}]},{"date":"2026-08-04","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":11.7788,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡羊座","degree":16.7167,"house":6,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":22.5026,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":27.2803,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":25.1741,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":7.6531,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6912,"house":5,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.1079,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2171,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.1026,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.43},{"transit_body":"Sun","natal_body":"Neptune","aspect":"trine","orb":0.54},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.67}],"moon_timepoints":[{"label":"morning","sign_ja":"牡羊座","degree":13.3819,"house":8,"aspects":[]},{"label":"noon","sign_ja":"牡羊座","degree":16.7167,"house":6,"aspects":[]},{"label":"night","sign_ja":"牡羊座","degree":21.7517,"house":1,"aspects":[]}]},{"date":"2026-08-05","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":12.7362,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡牛座","degree":0.2329,"house":6,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":23.6526,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":28.301,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":25.8454,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":7.8741,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6763,"house":5,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.138,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.2027,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.0795,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.21},{"transit_body":"Venus","natal_body":"Jupiter","aspect":"trine","orb":0.36},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.65},{"transit_body":"Sun","natal_body":"Neptune","aspect":"trine","orb":1.5}],"moon_timepoints":[{"label":"morning","sign_ja":"牡羊座","degree":26.8268,"house":9,"aspects":[]},{"label":"noon","sign_ja":"牡牛座","degree":0.2329,"house":6,"aspects":[]},{"label":"night","sign_ja":"牡牛座","degree":5.3765,"house":1,"aspects":[]}]},{"date":"2026-08-06","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":13.694,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡牛座","degree":14.0414,"house":7,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":24.8935,"house":9,"retrograde":false},"Venus":{"sign_ja":"乙女座","degree":29.3168,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":26.5156,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":8.095,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6596,"house":5,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.1673,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.1879,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.0564,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.01},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.63},{"transit_body":"Venus","natal_body":"Jupiter","aspect":"trine","orb":0.66}],"moon_timepoints":[{"label":"morning","sign_ja":"牡牛座","degree":10.5616,"house":9,"aspects":[{"natal_body":"Mercury","aspect":"trine","orb":0.16}]},{"label":"noon","sign_ja":"牡牛座","degree":14.0414,"house":7,"aspects":[]},{"label":"night","sign_ja":"牡牛座","degree":19.2953,"house":2,"aspects":[]}]},{"date":"2026-08-07","transiting_bodies":{"Sun":{"sign_ja":"獅子座","degree":14.6521,"house":9,"retrograde":false},"Moon":{"sign_ja":"牡牛座","degree":28.1409,"house":7,"retrograde":false},"Mercury":{"sign_ja":"蟹座","degree":26.2221,"house":9,"retrograde":false},"Venus":{"sign_ja":"天秤座","degree":0.3273,"house":11,"retrograde":false},"Mars":{"sign_ja":"双子座","degree":27.1845,"house":8,"retrograde":false},"Jupiter":{"sign_ja":"獅子座","degree":8.3159,"house":9,"retrograde":false},"Saturn":{"sign_ja":"牡羊座","degree":14.6414,"house":5,"retrograde":true},"Uranus":{"sign_ja":"双子座","degree":5.1959,"house":7,"retrograde":false},"Neptune":{"sign_ja":"牡羊座","degree":4.1726,"house":5,"retrograde":true},"Pluto":{"sign_ja":"水瓶座","degree":4.0334,"house":3,"retrograde":true}},"natal_aspects":[{"transit_body":"Jupiter","natal_body":"Saturn","aspect":"conjunction","orb":0.23},{"transit_body":"Moon","natal_body":"Jupiter","aspect":"conjunction","orb":0.52},{"transit_body":"Pluto","natal_body":"Uranus","aspect":"square","orb":0.6},{"transit_body":"Jupiter","natal_body":"Pluto","aspect":"sextile","orb":1.35}],"moon_timepoints":[{"label":"morning","sign_ja":"牡牛座","degree":24.5896,"house":10,"aspects":[{"natal_body":"Moon","aspect":"square","orb":0.65}]},{"label":"noon","sign_ja":"牡牛座","degree":28.1409,"house":7,"aspects":[{"natal_body":"Jupiter","aspect":"conjunction","orb":0.52}]},{"label":"night","sign_ja":"双子座","degree":3.4992,"house":2,"aspects":[{"natal_body":"Venus","aspect":"square","orb":0.88}]}]}],"today":{"selected_date":"2026-07-01"},"summary":{"overall_theme":"この31日間は、調整・見直し・境界線の整理が継続しやすい時期です。短期的な勢いより、違和感を確かめながら進めると扱いやすくなります。","key_dates":[{"date":"2026-07-01","theme":"自己表現、調整"},{"date":"2026-07-02","theme":"感情調整、調整"},{"date":"2026-07-03","theme":"自己表現、活用"},{"date":"2026-07-04","theme":"対人調整、調整"},{"date":"2026-07-05","theme":"感情調整、調整"},{"date":"2026-07-08","theme":"対人調整、調整"}],"caution_dates":["2026-07-01","2026-07-02","2026-07-03"],"easy_to_move_days":["2026-07-01","2026-07-03","2026-07-10"],"action_hints":["動きが出やすい日は、連絡・相談・意思表示などを前に進める候補日として使えます。","注意日には、即断よりも確認・調整・境界線の見直しを優先してください。","当日分の詳細を主根拠にし、31日サマリーは流れの強弱を読む補助として使ってください。"]}}}},"campaign":{"id":"note-2026-07","label":"2026年7月 note特典","target_month":"2026-07","start_date":"2026-07-01","end_date":"2026-08-07"}};

/* ---------- 定数・ヘルパー ---------- */
const C = {
  bg: "#14161E", panel: "#1C2030", panel2: "#232840", line: "#2E3348",
  text: "#E8E4D8", sub: "#9BA0B2", faint: "#6C7183",
  dawn: "#E8A87C", day: "#86BFCB", night: "#A79BD4",
  good: "#8FBF9F", hard: "#D98A93", conj: "#D4B475",
};
const SERIF = '"Shippori Mincho","Hiragino Mincho ProN","Yu Mincho","BIZ UDMincho",serif';
const SANS = '"Hiragino Kaku Gothic ProN","Yu Gothic",system-ui,sans-serif';

const SIGN_GLYPH = { 牡羊座:"♈", 牡牛座:"♉", 双子座:"♊", 蟹座:"♋", 獅子座:"♌", 乙女座:"♍", 天秤座:"♎", 蠍座:"♏", 射手座:"♐", 山羊座:"♑", 水瓶座:"♒", 魚座:"♓" };
const PLANET = {
  Sun:{g:"☉",ja:"太陽"}, Moon:{g:"☽",ja:"月"}, Mercury:{g:"☿",ja:"水星"}, Venus:{g:"♀",ja:"金星"},
  Mars:{g:"♂",ja:"火星"}, Jupiter:{g:"♃",ja:"木星"}, Saturn:{g:"♄",ja:"土星"}, Uranus:{g:"♅",ja:"天王星"},
  Neptune:{g:"♆",ja:"海王星"}, Pluto:{g:"♇",ja:"冥王星"}, "North Node":{g:"☊",ja:"Nノード"},
  "South Node":{g:"☋",ja:"Sノード"}, ASC:{g:"AC",ja:"ASC"}, MC:{g:"MC",ja:"MC"},
  Lilith:{g:"⚸",ja:"リリス"}, Chiron:{g:"⚷",ja:"キロン"}, Ceres:{g:"⚳",ja:"セレス"},
  Pallas:{g:"⚴",ja:"パラス"}, Juno:{g:"⚵",ja:"ジュノー"}, Vesta:{g:"⚶",ja:"ベスタ"}, Vertex:{g:"Vx",ja:"バーテックス"},
};
const ASPECT = {
  conjunction:{g:"☌",ja:"合",color:C.conj,tone:"neutral"},
  opposition:{g:"☍",ja:"オポジション",color:C.hard,tone:"hard"},
  square:{g:"□",ja:"スクエア",color:C.hard,tone:"hard"},
  trine:{g:"△",ja:"トライン",color:C.good,tone:"good"},
  sextile:{g:"⚹",ja:"セクスタイル",color:C.good,tone:"good"},
};
const TP = {
  morning:{ja:"朝",time:"6:00",color:C.dawn,grad:"linear-gradient(160deg,#2A2333,#3A2C33)"},
  noon:{ja:"昼",time:"12:00",color:C.day,grad:"linear-gradient(160deg,#1E2A38,#22333C)"},
  night:{ja:"夜",time:"21:00",color:C.night,grad:"linear-gradient(160deg,#1E2038,#262042)"},
};
const fmtDeg = d => `${Math.floor(d)}°${String(Math.round((d - Math.floor(d)) * 60)).padStart(2,"0")}′`;
const wdJa = ["日","月","火","水","木","金","土"];
const fmtDate = s => { const [y,m,d] = s.split("-").map(Number); return `${m}/${d}(${wdJa[new Date(y,m-1,d).getDay()]})`; };

const natal = DATA.systems.western.natal;
const asteroids = DATA.systems.western.asteroids;
const transit = DATA.systems.western.transit;
const summary = transit.summary;
const TODAY = transit.today.selected_date;

/* ---------- 共通UI ---------- */
const Eyebrow = ({children}) => (
  <div style={{fontSize:11,letterSpacing:"0.28em",color:C.faint,textTransform:"uppercase",marginBottom:6}}>{children}</div>
);
const H2 = ({children}) => (
  <h2 style={{fontFamily:SERIF,fontSize:22,fontWeight:600,color:C.text,margin:"0 0 14px",letterSpacing:"0.06em"}}>{children}</h2>
);
const Panel = ({children,style}) => (
  <div style={{background:C.panel,border:`1px solid ${C.line}`,borderRadius:10,padding:18,...style}}>{children}</div>
);
const AspectChip = ({a,dense}) => {
  const info = ASPECT[a.aspect];
  const t = PLANET[a.transit_body]||{g:"",ja:a.transit_body};
  const n = PLANET[a.natal_body]||{g:"",ja:a.natal_body};
  return (
    <span style={{display:"inline-flex",alignItems:"center",gap:5,fontSize:dense?11:12.5,
      background:C.panel2,border:`1px solid ${C.line}`,borderLeft:`3px solid ${info.color}`,
      borderRadius:6,padding:dense?"3px 7px":"4px 9px",color:C.text,whiteSpace:"nowrap"}}>
      <span style={{color:C.sub}}>T</span>{t.ja}
      <span style={{color:info.color,fontSize:dense?12:14}}>{info.g}</span>
      <span style={{color:C.sub}}>N</span>{n.ja}
      <span style={{color:C.faint,fontSize:10}}>orb {a.orb.toFixed(2)}</span>
    </span>
  );
};

/* ---------- ① 出生図ビューア ---------- */
function NatalView(){
  const bodies = Object.entries(natal.bodies);
  const el = natal.summary.elements, mo = natal.summary.modes;
  const bar = (label,val,max,color) => (
    <div key={label} style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
      <span style={{width:44,fontSize:12,color:C.sub}}>{label}</span>
      <div style={{flex:1,height:8,background:C.panel2,borderRadius:4,overflow:"hidden"}}>
        <div style={{width:`${(val/max)*100}%`,height:"100%",background:color,borderRadius:4}}/>
      </div>
      <span style={{width:16,fontSize:12,color:C.text,textAlign:"right"}}>{val}</span>
    </div>
  );
  const tightAspects = natal.aspects.filter(a=>a.orb<=2.2);
  return (
    <div>
      <div style={{display:"grid",gridTemplateColumns:"minmax(300px,1.4fr) minmax(240px,1fr)",gap:16}} className="grid-collapse">
        <Panel>
          <Eyebrow>Natal Bodies</Eyebrow>
          <H2>天体配置</H2>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13.5}}>
            <thead><tr style={{color:C.faint,fontSize:11,letterSpacing:"0.1em"}}>
              {["天体","サイン","度数","ハウス",""].map(h=><th key={h} style={{textAlign:"left",padding:"4px 6px",borderBottom:`1px solid ${C.line}`}}>{h}</th>)}
            </tr></thead>
            <tbody>
              {bodies.map(([k,b])=>(
                <tr key={k} style={{borderBottom:`1px solid ${C.line}55`}}>
                  <td style={{padding:"6px"}}><span style={{color:C.conj,marginRight:6,fontSize:15}}>{PLANET[k]?.g}</span>{PLANET[k]?.ja||k}</td>
                  <td style={{padding:"6px"}}><span style={{marginRight:4}}>{SIGN_GLYPH[b.sign_ja]}</span>{b.sign_ja}</td>
                  <td style={{padding:"6px",color:C.sub}}>{fmtDeg(b.degree)}</td>
                  <td style={{padding:"6px",color:C.sub}}>{b.house}室</td>
                  <td style={{padding:"6px",color:C.hard,fontSize:11}}>{b.retrograde?"R":""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          <Panel>
            <Eyebrow>Balance</Eyebrow>
            <H2>エレメント / モード</H2>
            {bar("火",el.fire,6,C.dawn)}{bar("地",el.earth,6,C.conj)}{bar("風",el.air,6,C.day)}{bar("水",el.water,6,C.night)}
            <div style={{height:10}}/>
            {bar("活動",mo.cardinal,6,C.day)}{bar("固定",mo.fixed,6,C.dawn)}{bar("柔軟",mo.mutable,6,C.night)}
            <div style={{marginTop:12,fontSize:12.5,color:C.sub}}>
              強調サイン: {natal.summary.dominant_signs.map(s=>`${s.sign_ja}(${s.count})`).join(" / ")}
            </div>
          </Panel>
          <Panel>
            <Eyebrow>Asteroids</Eyebrow>
            <H2>小惑星</H2>
            {Object.entries(asteroids).map(([k,b])=>(
              <div key={k} style={{display:"flex",justifyContent:"space-between",fontSize:13,padding:"4px 0",borderBottom:`1px solid ${C.line}44`}}>
                <span><span style={{color:C.night,marginRight:6}}>{PLANET[k]?.g}</span>{PLANET[k]?.ja||k}</span>
                <span style={{color:C.sub}}>{SIGN_GLYPH[b.sign_ja]} {b.sign_ja} {fmtDeg(b.degree)} / {b.house}室{b.retrograde?" R":""}</span>
              </div>
            ))}
          </Panel>
        </div>
      </div>
      <Panel style={{marginTop:16}}>
        <Eyebrow>Natal Aspects (orb ≤ 2.2)</Eyebrow>
        <H2>主要アスペクト</H2>
        <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
          {tightAspects.map((a,i)=>{
            const info=ASPECT[a.aspect];
            const b1=PLANET[a.body1]||{ja:a.body1}, b2=PLANET[a.body2]||{ja:a.body2};
            return <span key={i} style={{fontSize:12.5,background:C.panel2,border:`1px solid ${C.line}`,borderLeft:`3px solid ${info.color}`,borderRadius:6,padding:"4px 9px"}}>
              {b1.ja} <span style={{color:info.color}}>{info.g}</span> {b2.ja} <span style={{color:C.faint,fontSize:10}}>orb {a.orb.toFixed(2)}</span>
            </span>;
          })}
        </div>
      </Panel>
    </div>
  );
}

/* ---------- ② 38日カレンダー ---------- */
function CalendarView({onSelect,selected}){
  const days = transit.daily;
  const first = days[0].date;
  const [y,m,d] = first.split("-").map(Number);
  const lead = new Date(y,m-1,d).getDay();
  const cells = [...Array(lead).fill(null), ...days];
  const cautionSet = new Set(summary.caution_dates);
  const moveSet = new Set(summary.easy_to_move_days);
  const keyMap = Object.fromEntries(summary.key_dates.map(k=>[k.date,k.theme]));
  return (
    <div>
      <Panel style={{marginBottom:16}}>
        <Eyebrow>Overall Theme</Eyebrow>
        <div style={{fontFamily:SERIF,fontSize:15.5,lineHeight:1.9,color:C.text}}>{summary.overall_theme}</div>
        <div style={{display:"flex",gap:16,marginTop:12,fontSize:12,color:C.sub,flexWrap:"wrap"}}>
          <span><span style={{color:C.good}}>●</span> 動きやすい日</span>
          <span><span style={{color:C.hard}}>●</span> 注意したい日</span>
          <span><span style={{color:C.conj}}>◆</span> キーデート</span>
        </div>
      </Panel>
      <div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:6}}>
        {wdJa.map((w,i)=><div key={w} style={{textAlign:"center",fontSize:11,color:i===0?C.hard:i===6?C.day:C.faint,padding:"2px 0",letterSpacing:"0.2em"}}>{w}</div>)}
        {cells.map((day,i)=>{
          if(!day) return <div key={`b${i}`}/>;
          const dt = day.date;
          const isSel = dt===selected, isToday = dt===TODAY;
          const noonMoon = day.transiting_bodies.Moon;
          const hard = day.natal_aspects.filter(a=>ASPECT[a.aspect].tone==="hard"&&a.orb<=1).length;
          const good = day.natal_aspects.filter(a=>ASPECT[a.aspect].tone==="good"&&a.orb<=1).length;
          return (
            <button key={dt} onClick={()=>onSelect(dt)} style={{
              background:isSel?C.panel2:C.panel, border:`1px solid ${isSel?C.conj:isToday?C.dawn:C.line}`,
              borderRadius:8, padding:"8px 6px", cursor:"pointer", textAlign:"left", minHeight:74,
              color:C.text, fontFamily:SANS, position:"relative", transition:"border-color .15s",
            }}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline"}}>
                <span style={{fontFamily:SERIF,fontSize:15}}>{Number(dt.slice(8))}</span>
                <span style={{fontSize:9,color:C.faint}}>{dt.slice(5,7)}月</span>
              </div>
              <div style={{fontSize:11,color:C.sub,marginTop:2}}>☽ {SIGN_GLYPH[noonMoon.sign_ja]} {noonMoon.sign_ja.replace("座","")}</div>
              <div style={{display:"flex",gap:3,marginTop:5,alignItems:"center",flexWrap:"wrap"}}>
                {[...Array(good)].map((_,j)=><span key={`g${j}`} style={{width:5,height:5,borderRadius:3,background:C.good,display:"inline-block"}}/>)}
                {[...Array(hard)].map((_,j)=><span key={`h${j}`} style={{width:5,height:5,borderRadius:3,background:C.hard,display:"inline-block"}}/>)}
                {keyMap[dt] && <span style={{color:C.conj,fontSize:9}}>◆</span>}
              </div>
              {isToday && <span style={{position:"absolute",top:5,right:6,fontSize:8,color:C.dawn,letterSpacing:"0.1em"}}>今日</span>}
              {cautionSet.has(dt)&&<span style={{position:"absolute",bottom:5,right:6,fontSize:8,color:C.hard}}>注意</span>}
              {moveSet.has(dt)&&!cautionSet.has(dt)&&<span style={{position:"absolute",bottom:5,right:6,fontSize:8,color:C.good}}>動</span>}
            </button>
          );
        })}
      </div>
      <Panel style={{marginTop:16}}>
        <Eyebrow>Action Hints</Eyebrow>
        {summary.action_hints.map((h,i)=><div key={i} style={{fontSize:13.5,color:C.sub,lineHeight:1.9}}>・{h}</div>)}
      </Panel>
    </div>
  );
}

/* ---------- ③ 日別詳細（朝・昼・夜） ---------- */
function DayDetail({date,onNavigate,onAskAI}){
  const idx = transit.daily.findIndex(d=>d.date===date);
  const day = transit.daily[idx];
  if(!day) return null;
  const keyInfo = summary.key_dates.find(k=>k.date===date);
  return (
    <div>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:14,flexWrap:"wrap",gap:8}}>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <button onClick={()=>idx>0&&onNavigate(transit.daily[idx-1].date)} disabled={idx===0} style={navBtn(idx===0)}>←</button>
          <div>
            <div style={{fontFamily:SERIF,fontSize:24,letterSpacing:"0.08em"}}>{fmtDate(date)}</div>
            {keyInfo && <div style={{fontSize:12,color:C.conj}}>◆ {keyInfo.theme}</div>}
          </div>
          <button onClick={()=>idx<transit.daily.length-1&&onNavigate(transit.daily[idx+1].date)} disabled={idx===transit.daily.length-1} style={navBtn(idx===transit.daily.length-1)}>→</button>
        </div>
        <button onClick={()=>onAskAI(date)} style={{background:"transparent",border:`1px solid ${C.dawn}`,color:C.dawn,borderRadius:8,padding:"7px 14px",cursor:"pointer",fontSize:13,fontFamily:SANS}}>
          この日をAIに読ませる →
        </button>
      </div>

      {/* 朝・昼・夜の帯 — シグネチャ要素 */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:10,marginBottom:16}} className="grid-collapse">
        {day.moon_timepoints.map(tp=>{
          const t = TP[tp.label];
          return (
            <div key={tp.label} style={{background:t.grad,border:`1px solid ${C.line}`,borderTop:`2px solid ${t.color}`,borderRadius:10,padding:"14px 14px 12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline"}}>
                <span style={{fontFamily:SERIF,fontSize:17,color:t.color,letterSpacing:"0.15em"}}>{t.ja}</span>
                <span style={{fontSize:10,color:C.faint}}>{t.time}</span>
              </div>
              <div style={{fontSize:14,marginTop:8}}>☽ {SIGN_GLYPH[tp.sign_ja]} {tp.sign_ja} {fmtDeg(tp.degree)}</div>
              <div style={{fontSize:11.5,color:C.sub,marginTop:2}}>{tp.house}室</div>
              <div style={{marginTop:8,display:"flex",flexDirection:"column",gap:4}}>
                {tp.aspects.length===0
                  ? <span style={{fontSize:11,color:C.faint}}>月のタイトなアスペクトなし</span>
                  : tp.aspects.map((a,i)=>{
                      const info=ASPECT[a.aspect], n=PLANET[a.natal_body]||{ja:a.natal_body};
                      return <span key={i} style={{fontSize:12}}>
                        <span style={{color:info.color}}>{info.g}</span> N{n.ja}（{info.ja} orb {a.orb.toFixed(2)}）
                      </span>;
                    })}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1.1fr 1fr",gap:16}} className="grid-collapse">
        <Panel>
          <Eyebrow>Transit → Natal</Eyebrow>
          <H2>この日のアスペクト</H2>
          <div style={{display:"flex",flexDirection:"column",gap:7}}>
            {[...day.natal_aspects].sort((a,b)=>a.orb-b.orb).map((a,i)=><div key={i}><AspectChip a={a}/></div>)}
          </div>
        </Panel>
        <Panel>
          <Eyebrow>Transiting Bodies (12:00)</Eyebrow>
          <H2>運行天体</H2>
          {Object.entries(day.transiting_bodies).map(([k,b])=>(
            <div key={k} style={{display:"flex",justifyContent:"space-between",fontSize:13,padding:"4px 0",borderBottom:`1px solid ${C.line}44`}}>
              <span><span style={{color:C.conj,marginRight:6}}>{PLANET[k]?.g}</span>{PLANET[k]?.ja}</span>
              <span style={{color:C.sub}}>{SIGN_GLYPH[b.sign_ja]} {b.sign_ja} {fmtDeg(b.degree)} / {b.house}室{b.retrograde?<span style={{color:C.hard}}> R</span>:""}</span>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}
const navBtn = (disabled)=>({background:C.panel,border:`1px solid ${C.line}`,color:disabled?C.faint:C.text,borderRadius:8,width:34,height:34,cursor:disabled?"default":"pointer",fontSize:15});

/* ---------- ④ AI鑑定 ---------- */
const AI_SECTIONS = [
  {id:"overview",label:"全体像"},
  {id:"talent",label:"才能・強み"},
  {id:"pitfall",label:"つまずきやすいパターン"},
  {id:"work",label:"仕事・活動の向き"},
  {id:"relation",label:"人間関係の傾向"},
  {id:"flow38",label:"今後38日間の流れ"},
  {id:"selectedDay",label:"選択日の使い方（朝・昼・夜）"},
];

function buildPayload(sectionId, selectedDate){
  const compactBodies = Object.fromEntries(Object.entries(natal.bodies).map(([k,b])=>[k,{sign:b.sign_ja,deg:+b.degree.toFixed(1),house:b.house,r:b.retrograde}]));
  const compactAst = Object.fromEntries(Object.entries(asteroids).map(([k,b])=>[k,{sign:b.sign_ja,deg:+b.degree.toFixed(1),house:b.house}]));
  const tightNatal = natal.aspects.filter(a=>a.orb<=2.2);
  const base = {出生図:{天体:compactBodies,小惑星:compactAst,アスペクト:tightNatal,バランス:natal.summary}};
  if(sectionId==="flow38"){
    base.期間サマリー = summary;
    base.日別タイトアスペクト = transit.daily.map(d=>({date:d.date,aspects:d.natal_aspects.filter(a=>a.orb<=0.8)}));
  }
  if(sectionId==="selectedDay"){
    const day = transit.daily.find(d=>d.date===selectedDate);
    base.対象日 = {date:day.date, アスペクト:day.natal_aspects, 朝昼夜の月:day.moon_timepoints};
  }
  return base;
}

const AI_INSTRUCTIONS = {
  overview:"このホロスコープの全体像を、性質の傾向として400字程度でまとめてください。",
  talent:"才能・強みを3点、根拠となる配置を添えて説明してください。",
  pitfall:"つまずきやすいパターンを2〜3点、「どう使うとズレにくいか」の視点で説明してください。",
  work:"仕事・活動の向きを、具体的な活かし方とともに説明してください。",
  relation:"人間関係の傾向を、出生図の配置を根拠に説明してください。",
  flow38:"期間サマリーと日別タイトアスペクトをもとに、38日間の流れと「動きやすい日・注意したい日」を説明してください。基準日(2026-07-01)以降を未来として扱ってください。",
  selectedDay:"対象日のデータをもとに、朝・昼・夜それぞれの使い方を具体的な行動ヒントとして説明してください。",
};

function AIView({selectedDate}){
  const [results,setResults] = useState({});
  const [loading,setLoading] = useState(null);
  const [error,setError] = useState(null);

  const run = async (sec) => {
    setLoading(sec.id); setError(null);
    try{
      const payload = buildPayload(sec.id, selectedDate);
      const res = await fetch("https://api.anthropic.com/v1/messages",{
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          model:"claude-sonnet-4-6", max_tokens:1000,
          messages:[{role:"user",content:
`あなたは西洋占星術の鑑定者です。以下のJSONは計算済みデータです。
ルール: 計算結果を変更・再計算しない / この値のみを根拠にする / 断定しすぎず傾向・使い方として表現する / 「良い・悪い」ではなく「どう使うとズレにくいか」を優先 / 「ラッキー」等の軽い表現は避け具体的な行動ヒントに置き換える。
依頼: ${AI_INSTRUCTIONS[sec.id]}${sec.id==="selectedDay"?`（対象日: ${selectedDate}）`:""}
見出しや箇条書きを適度に使い、日本語で読みやすく書いてください。

データ:
${JSON.stringify(payload)}`}],
        }),
      });
      const data = await res.json();
      if(data.error) throw new Error(data.error.message||"APIエラー");
      const text = (data.content||[]).map(c=>c.type==="text"?c.text:"").join("\n");
      setResults(r=>({...r,[sec.id]:text}));
    }catch(e){ setError(`生成できませんでした: ${e.message}`); }
    setLoading(null);
  };

  return (
    <div>
      <Panel style={{marginBottom:16}}>
        <Eyebrow>AI Reading</Eyebrow>
        <H2>AI鑑定を生成する</H2>
        <div style={{fontSize:13,color:C.sub,marginBottom:12,lineHeight:1.8}}>
          読みたい項目を選ぶと、このYAMLの計算結果だけを根拠にClaudeが鑑定文を生成します。
          {selectedDate!==TODAY && <span>（選択日: <span style={{color:C.dawn}}>{fmtDate(selectedDate)}</span>）</span>}
        </div>
        <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
          {AI_SECTIONS.map(sec=>(
            <button key={sec.id} onClick={()=>run(sec)} disabled={loading!==null} style={{
              background:results[sec.id]?C.panel2:"transparent", color:loading===sec.id?C.faint:C.text,
              border:`1px solid ${results[sec.id]?C.conj:C.line}`, borderRadius:8, padding:"8px 14px",
              cursor:loading?"default":"pointer", fontSize:13, fontFamily:SANS,
            }}>
              {loading===sec.id?"生成中…":sec.label}{results[sec.id]&&" ✓"}
            </button>
          ))}
        </div>
        {error && <div style={{marginTop:10,fontSize:12.5,color:C.hard}}>{error}</div>}
      </Panel>
      {AI_SECTIONS.filter(s=>results[s.id]).map(sec=>(
        <Panel key={sec.id} style={{marginBottom:14}}>
          <Eyebrow>Reading</Eyebrow>
          <H2>{sec.label}</H2>
          <div style={{fontSize:14.5,lineHeight:2.05,color:C.text,whiteSpace:"pre-wrap",fontFamily:SANS}}>{results[sec.id]}</div>
        </Panel>
      ))}
    </div>
  );
}

/* ---------- ルート ---------- */
export default function App(){
  const [tab,setTab] = useState("calendar");
  const [selected,setSelected] = useState(TODAY);
  const tabs = [
    {id:"natal",label:"出生図"},
    {id:"calendar",label:"38日カレンダー"},
    {id:"day",label:"日別詳細"},
    {id:"ai",label:"AI鑑定"},
  ];
  return (
    <div style={{minHeight:"100vh",background:C.bg,color:C.text,fontFamily:SANS}}>
      <style>{`
        @media (max-width: 720px){ .grid-collapse{ grid-template-columns: 1fr !important; } }
        button:focus-visible{ outline: 2px solid ${C.dawn}; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce){ *{ transition: none !important; } }
      `}</style>
      {/* ヘッダー */}
      <header style={{borderBottom:`1px solid ${C.line}`,padding:"22px 24px 0",maxWidth:1080,margin:"0 auto"}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-end",flexWrap:"wrap",gap:10}}>
          <div>
            <Eyebrow>Nanami Products — Western 38days Transit</Eyebrow>
            <h1 style={{fontFamily:SERIF,fontSize:30,fontWeight:600,margin:0,letterSpacing:"0.1em"}}>星読みの暦</h1>
            <div style={{fontSize:12.5,color:C.sub,margin:"8px 0 0"}}>
              {DATA.input.title} ／ {DATA.input.birth_date} {DATA.input.birth_time} 生・{DATA.input.birth_place}（出生時刻: 正確）
            </div>
          </div>
          <div style={{fontSize:11.5,color:C.faint,textAlign:"right"}}>
            期間 {transit.period.start_date} — {transit.period.end_date}<br/>
            Swiss Ephemeris / Placidus / Asia&#47;Tokyo
          </div>
        </div>
        {/* 朝→昼→夜のホライズンライン（シグネチャ） */}
        <div style={{height:3,margin:"16px 0 0",borderRadius:2,background:`linear-gradient(90deg,${C.dawn},${C.day} 45%,${C.night})`}}/>
        <nav style={{display:"flex",gap:4,marginTop:0}}>
          {tabs.map(t=>(
            <button key={t.id} onClick={()=>setTab(t.id)} style={{
              background:"transparent",border:"none",borderBottom:`2px solid ${tab===t.id?C.dawn:"transparent"}`,
              color:tab===t.id?C.text:C.sub,padding:"14px 14px 12px",fontSize:14,cursor:"pointer",fontFamily:SANS,letterSpacing:"0.05em",
            }}>{t.label}</button>
          ))}
        </nav>
      </header>
      <main style={{maxWidth:1080,margin:"0 auto",padding:"24px"}}>
        {tab==="natal" && <NatalView/>}
        {tab==="calendar" && <CalendarView selected={selected} onSelect={(d)=>{setSelected(d);setTab("day");}}/>}
        {tab==="day" && <DayDetail date={selected} onNavigate={setSelected} onAskAI={(d)=>{setSelected(d);setTab("ai");}}/>}
        {tab==="ai" && <AIView selectedDate={selected}/>}
      </main>
      <footer style={{maxWidth:1080,margin:"0 auto",padding:"0 24px 28px",fontSize:11,color:C.faint,lineHeight:1.8}}>
        天体位置・アスペクトはYAML内の計算済みデータをそのまま表示しています（再計算なし）。AI鑑定は傾向・使い方の参考情報であり、断定的な予言ではありません。
      </footer>
    </div>
  );
}
