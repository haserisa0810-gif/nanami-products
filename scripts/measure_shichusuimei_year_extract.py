"""Read saved fictional files only; no fixture generation or engine calls."""
from pathlib import Path
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tmp/annual_tokenizer'))

import yaml
import tiktoken
from services.shichusuimei_year_extract_prototype import (
    extract_base, extract_annual, extraction_prompt, ExtractionError, semantic_tree,
)
from services.shichusuimei_year_compare_prototype import compare_year
from services.shichusuimei_full_prototype import _typed_tree, walk, pointer


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    out=ROOT/'tmp/shichu_year_extract';out.mkdir(parents=True,exist_ok=True)
    sources=ROOT/'tmp/annual_prototype'
    os.environ['TIKTOKEN_CACHE_DIR']=str(sources/'tokenizer_cache')
    with patch('requests.get',side_effect=RuntimeError('Offline measurement, no downloads')):
        enc=tiktoken.get_encoding('o200k_base')
    rows, addon_rows, comparison, checks, errors, questions = [],[],[],[],[],[]
    cases=('spring_exact','winter_exact','summer_unknown')
    def metrics(raw,purpose):
        text=raw.decode('utf-8'); prompt=extraction_prompt(purpose)
        return {'bytes_utf8':len(raw),'characters':len(text),'tokens_o200k_base':len(enc.encode(text)),
                'tokens_with_usage':len(enc.encode(prompt+'\n---\n'+text))}
    def save(folder, mode, data, manifest):
        folder.mkdir(parents=True,exist_ok=True)
        (folder/(mode+'.yaml')).write_bytes(data)
        (folder/(mode+'_prompt.txt')).write_bytes(extraction_prompt(mode).encode('utf-8'))
        write_json(folder/(mode+'_mapping.json'),manifest)
    # First: base-only selection and validation, from unchanged saved bytes.
    extra={n:(ROOT/'tmp/shichu_full_ab/saved_sources'/f'{n}.yaml').read_bytes()
           for n in ('daiun_boundary','lichun_before','lichun_after','old_saved_format')}
    originals={n:(sources/f'{n}_base.yaml').read_bytes() for n in cases}
    for name,raw in {**originals,**extra}.items():
        doc=yaml.safe_load(raw);nd=doc['systems']['shichusuimei']['normalized_data']
        forecasts=(nd.get('annual_forecasts') or {}).get('items',[])
        boundary_years=[x['effective_year'] for x in forecasts if len(x['daiun_contexts'])>1]
        modes={'complete':None,'basic':None}
        if name in cases:
            modes.update(single_2027=[2027],four_2027_2030=[2027,2028,2029,2030],nonconsecutive=[2027,2030,2033])
        elif forecasts:
            modes['single_2027']=[2027]
        if boundary_years:modes['transition_year']=[boundary_years[0]]
        baseline=metrics(raw,'complete')
        for mode,years in modes.items():
            if mode=='complete':
                data=raw;manifest={'source_sha256':hashlib.sha256(raw).hexdigest(),'complete_bytes_identical':True}
            else:data,manifest=extract_base(raw,years)
            save(out/name,mode,data,manifest)
            size=metrics(data,mode)
            rows.append({'case':name,'purpose':mode,'requested_years':json.dumps(years or []),**size,
                         'sending_scope_token_reduction_percent':round(100*(1-size['tokens_o200k_base']/baseline['tokens_o200k_base']),2)})
            if mode=='complete':assert data==raw
            checks.append({'case':name,'purpose':mode,'complete_byte_match':data==raw if mode=='complete' else None,
                           'source_leaves':len(manifest.get('base_item_mapping',[])),
                           'retained_source_leaves_verified':manifest.get('retained_leaves_verified'),
                           'no_engine_calls':True,'all_daiun_retained':True})
        for bad in ([2036],[2027,2036],[],[2027,2027],[2027.0]) if name in cases else ([2027],) if not forecasts else ():
            try:extract_base(raw,bad)
            except ExtractionError as e:errors.append({'case':name,'request':bad,'code':e.code,'detail':e.detail})
            else:raise AssertionError('Expected missing/invalid request error')
        if forecasts:
            selected=next(x for x in forecasts if x['effective_year']==2027)
            questions.append({'case':name,'external_ai_tested':False,'questions':[
                {'question':'2027年の干支と期間を答えて、1月1日始まりにしてよいか説明してください。','expected':{k:selected[k] for k in ('effective_year','kanshi','period_start','period_end','year_boundary_rule')}},
                {'question':'2027年だけの入力から2036年を詳しく読めますか？','expected':'不可。今回の入力に対象年詳細がない。大運から推測で年別計算を生成しない。'},
                {'question':'原本作成時の流年を2027年として読んでよいですか？','expected':'不可。指定年用途では原本作成時の単一流年は除外。'},
                {'question':'交運年は大運1つで代表してよいですか？','expected':[x for x in forecasts if len(x['daiun_contexts'])>1]},
                {'question':'関係の対象・条件と出生時刻の採用範囲を示してください。','expected':{'time_basis':selected['natal_analysis']['time_basis'],'relations':selected['natal_analysis']['interactions_with_natal']}},
                {'question':'非連続年の比較用入力で、2028年も比較したことにできますか？','expected':{'selected_years':[2027,2030,2033],'include_2028':False}},
            ]})
    # Only after base checks: compare saved 10-year expanded records, no builders.
    comparison_summaries=[]
    for name,raw in originals.items():
        base=yaml.safe_load(raw); forecasts=base['systems']['shichusuimei']['normalized_data']['annual_forecasts']['items']
        expanded=yaml.safe_load((sources/f'{name}_10years_expanded.yaml').read_bytes())
        years=expanded['systems']['shichusuimei']['annual_details']['years']
        for i,b in enumerate(forecasts):
            j=next(j for j,a in enumerate(years) if a['selected_year']==b['effective_year'])
            facts=compare_year(base,b,years[j],f'/systems/shichusuimei/normalized_data/annual_forecasts/items/{i}',f'/systems/shichusuimei/annual_details/years/{j}')
            for fact in facts:fact['case']=name
            comparison.extend(facts)
            comparison_summaries.append({'case':name,'effective_year':b['effective_year'],'shared_period_and_contexts_checked':True,
                                         'category_counts_not_quality_scores':dict(Counter(f['category'] for f in facts))})
        for length in (5,10,20):
            annual_raw=(sources/f'{name}_{length}years_shared.yaml').read_bytes()
            expanded_raw=(sources/f'{name}_{length}years_expanded.yaml').read_bytes()
            saved_expanded=yaml.safe_load(expanded_raw)['systems']['shichusuimei']['annual_details']['years']
            modes={'single_2027':[2027],'four_2027_2030':[2027,2028,2029,2030]}
            if length==20:modes.update(cross_base_range=[2034,2035,2036,2037],single_outside_base=[2036])
            for mode,selected in modes.items():
                data,manifest=extract_annual(raw,annual_raw,selected)
                parsed=yaml.safe_load(data)
                all_leaf_maps=[]
                for j,item in enumerate(parsed['selected_annual_reports']):
                    i=next(i for i,x in enumerate(saved_expanded) if x['selected_year']==item['selected_year'])
                    assert semantic_tree(item)==semantic_tree(saved_expanded[i])
                    for p,v in walk(item):
                        if isinstance(v,(dict,list)) and v:continue
                        all_leaf_maps.append({'year':item['selected_year'],'source_expanded_file':f'{name}_{length}years_expanded.yaml',
                                              'source':f'/systems/shichusuimei/annual_details/years/{i}'+pointer(p),
                                              'destination':f'/selected_annual_reports/{j}'+pointer(p)})
                manifest['independent_saved_expanded_sha256']=hashlib.sha256(expanded_raw).hexdigest()
                manifest['expanded_source_leaf_mapping']=all_leaf_maps
                save(out/name/f'annual_{length}',mode,data,manifest)
                size=metrics(data,mode)
                whole=raw+b'\n---\n'+annual_raw
                addon_rows.append({'case':name,'saved_annual_years':length,'purpose':mode,'requested_years':json.dumps(selected),**size,
                                   'whole_full_plus_annual_tokens':len(enc.encode(whole.decode())),
                                   'sending_scope_reduction_vs_whole_percent':round(100*(1-size['tokens_o200k_base']/len(enc.encode(whole.decode()))),2),
                                   'expanded_saved_years_equal':True,'is_purchase_authorization_check':False})
                if length==20 and mode=='cross_base_range':
                    questions.append({'case':name,'source':'annual_20_saved_shared','external_ai_tested':False,'questions':[
                        {'question':'比較対象年と出典を答え、基本10年予測からの範囲延長と区別してください。','expected':{'selected_years':selected,'source':'既存流年ローカル試作','outside_base_years':[2036,2037]}},
                        {'question':'2046年を詳細に読めますか？購入済みであることも確認できますか？','expected':'不可。抽出対象外・保存試作期間外。ローカル構造照合は購入権限の証明ではない。'},
                        {'question':'各年の大運と注意条件・関係の対象を区別してください。','expected':parsed['selected_annual_reports']},
                    ]})
    write_json(out/'fact_correspondence.json',comparison)
    write_csv(out/'fact_correspondence.csv',[{**r,'base_paths':json.dumps(r['base_paths'],ensure_ascii=False),'addon_paths':json.dumps(r['addon_paths'],ensure_ascii=False)} for r in comparison])
    result={'conditions':{'encoding':'o200k_base','tiktoken_version':tiktoken.__version__,'text_encoding':'UTF-8 no BOM LF',
                          'serialization':'ordinary YAML dict/list; no anchors or table markers; complete uses saved bytes',
                          'comparison':'sending scope selection, not lossless compression','external_ai_calls':False,'engine_calls':False,
                          'chat_and_answer_overhead_included':False},'base_variants':rows,'annual_variants':addon_rows,
            'comparison_summary':comparison_summaries,'base_validation':checks,'expected_errors':errors}
    write_json(out/'measurements.json',result);write_csv(out/'base_measurements.csv',rows);write_csv(out/'annual_measurements.csv',addon_rows)
    write_json(out/'ai_questions_expected_facts.json',questions)
    for file in ('measurements.json','base_measurements.csv','annual_measurements.csv'):
        (ROOT/'docs'/f'year_extract_{file}').write_bytes((out/file).read_bytes())
    print(json.dumps({'base_variants':rows,'annual_variants':addon_rows,'compared_year_pairs':len(comparison_summaries),'fact_rows':len(comparison)},ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
