"""Conservative fact correspondence for saved natal forecasts and annual trials."""
from services.shichusuimei_full_prototype import _typed_tree, walk, pointer
from services.shichusuimei_year_extract_prototype import validate_annual_match

CATEGORIES = {"same_meaning": "両者に同じ意味の情報がある", "base_only": "基本側だけ",
              "addon_only": "追加側だけ", "comparison_pending": "計算方式や意味の比較が未完了"}


def compare_year(base_doc, forecast, report, base_path, addon_path):
    """Each source leaf is covered, plus exact shared facts and pair witnesses.

    Similar keys alone do not establish equivalence. Group relations remain
    pending: their witness grouping and partial/full policies differ.
    """
    validate_annual_match(base_doc, report)
    rows = []
    base_covered, addon_covered = set(), set()
    def descendants(value, prefix):
        return [prefix + pointer(p) if p else prefix for p,v in walk(value)
                if not isinstance(v, (dict,list)) or not v]
    def add(fact, bp, ap, category, reason, b=None, a=None):
        rows.append({"effective_year": forecast["effective_year"], "fact": fact,
                     "category": category, "category_ja": CATEGORIES[category],
                     "base_paths": bp, "addon_paths": ap, "reason": reason,
                     "compared_values_equal": _typed_tree(b) == _typed_tree(a) if b is not None and a is not None else None})
        base_covered.update(bp); addon_covered.update(ap)
    def exact(fact,bp,ap,b,a):
        equal = _typed_tree(b)==_typed_tree(a)
        add(fact,[bp],[ap],"same_meaning" if equal else "comparison_pending",
            "同じ命式・年・対象で保存値の型・値が一致" if equal else "保存値差。黙って統合しない",b,a)
    for k in ("effective_year","kanshi","period_start","period_end"):
        exact(k,base_path+'/'+k,addon_path+'/annual/'+k,forecast[k],report['annual'][k])
    exact('流年天干の十神',base_path+'/natal_analysis/stem_ten_god',addon_path+'/annual/ten_god_to_day_master',forecast['natal_analysis']['stem_ten_god'],report['annual']['ten_god_to_day_master'])
    exact('時柱採用基準',base_path+'/natal_analysis/time_basis',addon_path+'/calculation/natal_time_basis',forecast['natal_analysis']['time_basis'],report['calculation']['natal_time_basis'])
    exact('立春基準',base_path+'/year_boundary_rule',addon_path+'/calculation/year_boundary_rule',forecast['year_boundary_rule'],report['calculation']['year_boundary_rule'])
    exact('大運選択方式',base_path+'/daiun_selection_method',addon_path+'/calculation/daiun_selection_method',forecast['daiun_selection_method'],report['calculation']['daiun_selection_method'])
    exact('年内交運フラグ',base_path+'/daiun_boundary_in_window',addon_path+'/daiun/boundary_in_selected_year',forecast['daiun_boundary_in_window'],report['daiun']['boundary_in_selected_year'])
    for i,bc in enumerate(forecast['daiun_contexts']):
        j=next(j for j,c in enumerate(report['daiun']['contexts']) if c['index']==bc['index'])
        ac=report['daiun']['contexts'][j]
        for k in ('index','kanshi','age_from','age_to','overlap_start_approx','overlap_end_approx'):
            exact(f"大運{bc['index']}:{k}",f'{base_path}/daiun_contexts/{i}/{k}',f'{addon_path}/daiun/contexts/{j}/{k}',bc[k],ac[k])
    # Pair projections: preserve multiplicity and explicit target identities.
    natal=(base_doc['systems']['shichusuimei']['normalized_data']['pillars'])
    def pair_signature(r,incoming,context=None):
        participants=[]
        for side in ('left','right'):
            p=r[side]; name=p['name']
            if name=='luck': name=incoming
            if name=='current_daiun': name='daiun'
            if name=='annual': kanshi=forecast['kanshi']
            elif name=='daiun': kanshi=context['kanshi']
            else:
                value=natal[name]; kanshi=value['kanshi'] if isinstance(value,dict) else value
            if p.get('kanshi') and p['kanshi']!=kanshi:
                return ('participant_value_conflict', str(r))
            participants.append((name,context['index'] if name=='daiun' else None,kanshi))
        # All compared pair rules here use an unordered participant set in
        # the existing engines. Original directional fields remain untouched.
        return (r['type'],r.get('element'),tuple(sorted(participants,key=str)))
    def pairs(brel,arel,bprefix,aprefix,incoming,context=None):
        a_pairs=[(j,r) for j,r in enumerate(arel) if 'left' in r and 'right' in r
                 and (context is None or r.get('daiun_index')==context['index'])]
        used=set()
        for i,b in enumerate(brel):
            sig=pair_signature(b,incoming,context)
            hit=next(((j,a) for j,a in a_pairs if j not in used and pair_signature(a,incoming,context)==sig),None)
            if hit:
                j,a=hit; used.add(j)
                shared_keys=['type','element']
                if b.get('detail')==a.get('detail'):shared_keys.append('detail')
                bpaths=[bprefix+f'/{i}/'+k for k in shared_keys if k in b]
                apaths=[aprefix+f'/{j}/'+k for k in shared_keys if k in a]
                bpaths+=descendants(b['left'],bprefix+f'/{i}/left')+descendants(b['right'],bprefix+f'/{i}/right')
                apaths+=descendants(a['left'],aprefix+f'/{j}/left')+descendants(a['right'],aprefix+f'/{j}/right')
                add('二者関係の型・干支・対象集合',bpaths,apaths,'same_meaning','保存された参加者を元の年・大運・原局へ照合。条件・合化判定・target_ten_godsはこの同値判定に含めない')
    analysis=forecast['natal_analysis']['interactions_with_natal']
    for key in ('branch_relations','stem_relations'):
        pairs(analysis[key],report['interactions']['natal_annual'],base_path+'/natal_analysis/interactions_with_natal/'+key,addon_path+'/interactions/natal_annual','annual')
    for i,c in enumerate(forecast['daiun_contexts']):
        for key in ('branch_relations','stem_relations'):
            pairs(c['analysis']['interactions_with_daiun'][key],report['interactions']['daiun_annual'],f'{base_path}/daiun_contexts/{i}/analysis/interactions_with_daiun/{key}',addon_path+'/interactions/daiun_annual','annual',c)
    nd=base_doc['systems']['shichusuimei']['normalized_data']
    for label,bp,ap,b,a in (
        ('原局の空亡地支','/systems/shichusuimei/normalized_data/kubo/empty_branches',addon_path+'/kubo/empty_branches',nd['kubo']['empty_branches'],report['kubo']['empty_branches']),
        ('原局の五行参考値','/systems/shichusuimei/normalized_data/five_elements',addon_path+'/five_elements/natal',nd['five_elements'],report['five_elements']['natal']),
    ):
        add(label,descendants(b,bp),descendants(a,ap),'same_meaning','追加が基本の保存値を参照コピー。時刻不明の従来4柱参考値である注意も保持',b,a)
    bh=nd['kubo']['hit_pillars'];ah=report['kubo']['natal_hits']
    if not nd.get('time_sensitive_reference'):
        add('原局の空亡該当柱',descendants(bh,'/systems/shichusuimei/normalized_data/kubo/hit_pillars'),descendants(ah,addon_path+'/kubo/natal_hits'),'same_meaning' if bh==ah else 'comparison_pending','原局対象・時柱採用が同じ場合の保存該当柱',bh,ah)
    for root,label,value,path in (
        ('base','原局全体の構造分析',base_doc['systems']['shichusuimei']['normalized_data'].get('structural_analysis'),'/systems/shichusuimei/normalized_data/structural_analysis'),
        ('base','全大運の保存済み構造分析',base_doc['systems']['shichusuimei']['normalized_data']['daiun'],'/systems/shichusuimei/normalized_data/daiun'),
    ):
        add(label,[path],[], 'base_only','基本内の共通参照。追加ファイルは同じ基本Fullとの併用を要求し、全内容の複製を含まない')
    # Remaining leaves retain uncertainty where semantics were not proved.
    for side,doc,prefix,covered in (('base',forecast,base_path,base_covered),('addon',report,addon_path,addon_covered)):
        for p,v in walk(doc):
            if isinstance(v,(dict,list)) and v:continue
            path=prefix+pointer(p)
            if path in covered:continue
            category='comparison_pending'; reason='対象・条件・表現・グループ化が異なるか、意味の全対応を未証明'
            if side=='base' and any(k in p for k in ('stem_actions','exposed_natal_hidden_stems','incoming_rooting','activated_ten_gods','branch_ten_gods','target_ten_gods','combination_screening')):
                category='base_only'; reason='保存年別の生剋・透出・根・十神活性・対象十神・合化条件等。追加に同じ方式の年別項目がない'
            if side=='addon' and (p[:2] in (('kubo','annual_hit'),('kubo','daiun_hits')) or p[:2]==('annual','twelve_fortune_to_day_master') or p[:2]==('daiun','uncovered_before_first_daiun')):
                category='addon_only'; reason='指定年／大運の明示フラグ・十二運・起運前区間。基本年別項目に同じ明示出力はない（原局の空亡は基本にある）'
            if side=='addon' and p[0]=='five_elements':
                reason='参考個数。基本の季節重み付きスコアと方式・単位が違う。原局個数だけは共通原本と別途照合済み'
            if 'element_changes' in p or 'combined_element_scores' in p:
                reason='基本の季節重み付きスコアと追加の参考個数は同じ数値量ではない'
            add('保存項目:'+('/'.join(map(str,p))),[path] if side=='base' else [],[path] if side=='addon' else [],category,reason)
    return rows
