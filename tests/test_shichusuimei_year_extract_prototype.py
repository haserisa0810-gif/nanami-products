from copy import deepcopy
import hashlib
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "shichusuimei"

import pytest
import yaml

from services.shichusuimei_full_prototype import _typed_tree, walk
from services.shichusuimei_year_extract_prototype import extract_base, extract_annual, dump_extraction, ExtractionError, semantic_tree
from services.shichusuimei_annual_prototype import expand_shared_year


@pytest.fixture(scope="module")
def raw():
    return (FIXTURES / "spring_exact_base.yaml").read_bytes()


@pytest.fixture(scope="module")
def addon():
    return (FIXTURES / "spring_exact_20years_shared.yaml").read_bytes()


def test_base_single_and_multiple_years_preserve_all_selected_material(raw):
    source=yaml.safe_load(raw); nd=source['systems']['shichusuimei']['normalized_data']
    for years in ([2027], [2027,2028,2029,2030], [2033,2027,2030]):
        data,manifest=extract_base(raw,years); doc=yaml.safe_load(data)
        assert [y['effective_year'] for y in doc['selected_base_forecasts']]==years
        for item in doc['selected_base_forecasts']:
            saved=next(x for x in nd['annual_forecasts']['items'] if x['effective_year']==item['effective_year'])
            assert _typed_tree(item)==_typed_tree(saved)
        common=doc['common']['systems']['shichusuimei']['normalized_data']
        assert _typed_tree(common['daiun'])==_typed_tree(nd['daiun'])
        assert _typed_tree(common['structural_analysis'])==_typed_tree(nd['structural_analysis'])
        assert not any(p and p[-1] in ('annual_forecasts','annual_fortune') for p,v in walk(doc['common']))
        assert manifest['base_sha256']==hashlib.sha256(raw).hexdigest()
        assert b'__local_trial_table__' not in data
        assert not any(isinstance(t,(yaml.tokens.AnchorToken,yaml.tokens.AliasToken)) for t in yaml.scan(data))


def test_basic_keeps_original_current_annual_and_independent_compatibility(raw):
    source=yaml.safe_load(raw); data,manifest=extract_base(raw); doc=yaml.safe_load(data)
    sh=doc['common']['systems']['shichusuimei']
    assert _typed_tree(sh['normalized_data']['annual_fortune'])==_typed_tree(source['systems']['shichusuimei']['normalized_data']['annual_fortune'])
    assert sh['features']['strength']==source['systems']['shichusuimei']['features']['strength']
    assert sh['raw']==source['systems']['shichusuimei']['raw']
    assert 'annual_forecasts' not in sh['normalized_data']
    assert not doc['local_year_extraction']['included_years']


@pytest.mark.parametrize('years',[[],[True],['2027'],[2027.0],[2027,2027],[2027,2036],2027,[None]])
def test_invalid_or_partial_requests_never_emit_partial_output(raw,years):
    with pytest.raises(ExtractionError):extract_base(raw,years)


def test_year_selection_uses_stored_effective_year_not_array_position(raw):
    source=yaml.safe_load(raw); source['systems']['shichusuimei']['normalized_data']['annual_forecasts']['items'].reverse()
    data,_=extract_base(dump_extraction(source),[2027])
    assert yaml.safe_load(data)['selected_base_forecasts'][0]['effective_year']==2027


def test_duplicate_saved_year_is_rejected(raw):
    source=yaml.safe_load(raw); items=source['systems']['shichusuimei']['normalized_data']['annual_forecasts']['items']
    items.append(deepcopy(items[0]))
    with pytest.raises(ExtractionError,match='ambiguous_source_year'):extract_base(dump_extraction(source),[2027])


def test_identity_and_repeated_relationship_occurrences_are_preserved():
    from tests.test_shichusuimei_full_prototype import identity_fixture
    source=identity_fixture(); raw=dump_extraction(source)
    data,_=extract_base(raw,[2086,2026]); result=yaml.safe_load(data)
    assert [i['effective_year'] for i in result['selected_base_forecasts']]==[2086,2026]
    assert all(len(i['natal_analysis']['relations'])==3 for i in result['selected_base_forecasts'])
    assert list(result['common']['systems']['shichusuimei']['normalized_data']['pillars'])==['year','month','day','hour']


def test_unknown_time_and_transition_year_keep_all_conditions():
    raw=(FIXTURES / "summer_unknown_base.yaml").read_bytes(); source=yaml.safe_load(raw)
    nd=source['systems']['shichusuimei']['normalized_data']
    y=next(i['effective_year'] for i in nd['annual_forecasts']['items'] if len(i['daiun_contexts'])>1)
    data,_=extract_base(raw,[y]); doc=yaml.safe_load(data)
    assert len(doc['selected_base_forecasts'][0]['daiun_contexts'])==2
    assert doc['selected_base_forecasts'][0]['natal_analysis']['time_basis']=='three_pillars_hour_excluded'
    assert doc['common']['systems']['shichusuimei']['normalized_data']['time_sensitive_reference']==nd['time_sensitive_reference']


def test_old_missing_years_not_filled_with_new_engine(raw):
    source=yaml.safe_load(raw); source['systems']['shichusuimei']['normalized_data'].pop('annual_forecasts')
    old=dump_extraction(source); data,_=extract_base(old)
    assert 'annual_forecasts' in yaml.safe_load(data)['local_year_extraction']['source']['missing_original_sections']
    with pytest.raises(ExtractionError,match='years_not_saved'):extract_base(old,[2027])


def test_no_engine_calls_or_source_mutation(raw,addon,monkeypatch):
    from services import shichusuimei_calc as core,shichusuimei_annual_report as annual
    monkeypatch.setattr(core,'calc_shichusuimei_from_payload',lambda *a,**k:pytest.fail('No engine calls'))
    monkeypatch.setattr(annual,'build_annual_fortune_report',lambda *a,**k:pytest.fail('No annual calculations'))
    original=raw[:],addon[:]
    extract_base(raw,[2027]); extract_annual(raw,addon,[2034,2035,2036,2037])
    assert original==(raw,addon)


def test_shared_and_expanded_sources_produce_same_year_records(raw,addon):
    expanded=(FIXTURES / "spring_exact_20years_expanded.yaml").read_bytes()
    a,_=extract_annual(raw,addon,[2033,2034,2035,2036]); b,_=extract_annual(raw,expanded,[2033,2034,2035,2036])
    a,b=yaml.safe_load(a),yaml.safe_load(b)
    assert semantic_tree(a['selected_annual_reports'])==semantic_tree(b['selected_annual_reports'])
    assert a['common']==b['common']
    assert not any(p and p[-1] in ('daiun_ref','daiun_catalog','annual_forecasts','annual_fortune') for p,v in walk(a['common']))
    saved=yaml.safe_load(addon)
    for item in a['selected_annual_reports']:
        assert _typed_tree(item)==_typed_tree(expand_shared_year(saved,item['selected_year']))


@pytest.mark.parametrize('kind',['id','period','time_basis','daiun_interval','natal_pillar','missing_reference','wrong_reference','missing_context','wrong_year','relation_rule','relation_target'])
def test_annual_conflict_or_missing_reference_is_reported(raw,addon,kind):
    doc=yaml.safe_load(addon); details=doc['systems']['shichusuimei']['annual_details']; item=details['years'][1]
    ref=item['daiun']['contexts'][0]['daiun_ref']
    if kind=='id':details['base_reference']['chart_id']='different'
    elif kind=='period':item['annual']['period_start']='2027-02-05T00:00:00+09:00'
    elif kind=='time_basis':details['calculation']['natal_time_basis']='three_pillars_hour_excluded'
    elif kind=='natal_pillar':details['base_reference']['pillars']['day']='甲子'
    elif kind=='daiun_interval':item['daiun']['contexts'][0]['overlap_end_approx']='2027-02-05T00:00:00+09:00'
    elif kind=='missing_reference':details['daiun_catalog'].pop(ref)
    elif kind=='wrong_reference':item['interactions']['natal_daiun_refs']=[]
    elif kind=='missing_context':item['daiun']['contexts']=[]
    elif kind=='wrong_year':item['annual']['effective_year']=2028
    elif kind=='relation_rule':item['interactions']['natal_annual'][0]['type']='incorrect_saved_rule'
    elif kind=='relation_target':item['interactions']['natal_annual'][0]['left']['kanshi']='甲子'
    with pytest.raises(ExtractionError):extract_annual(raw,dump_extraction(doc),[2027])


def test_addon_missing_year_and_wrong_product_are_errors(raw,addon):
    with pytest.raises(ExtractionError,match='years_not_saved'):extract_annual(raw,addon,[2027,2046])
    doc=yaml.safe_load(addon);doc['meta']['product_type']='western_full'
    with pytest.raises(ExtractionError,match='wrong_source_type'):extract_annual(raw,dump_extraction(doc),[2027])


@pytest.mark.parametrize('kind',['year_period','pillar','context','compatibility_leak'])
def test_contradictory_saved_forecast_or_hidden_copy_is_not_exported(raw,kind):
    doc=yaml.safe_load(raw);sh=doc['systems']['shichusuimei'];item=sh['normalized_data']['annual_forecasts']['items'][1]
    if kind=='year_period':item['period_start']='2028-02-04T00:00:00+09:00'
    elif kind=='pillar':item['natal_analysis']['pillar']='甲子'
    elif kind=='context':item['daiun_contexts']=[]
    elif kind=='compatibility_leak':sh['features']['unexpected_annual_copy']=deepcopy(sh['normalized_data']['annual_forecasts']['items'])
    with pytest.raises(ExtractionError):extract_base(dump_extraction(doc),[2027])


def test_correspondence_covers_each_saved_year_leaf_without_claiming_superset(raw,addon):
    from services.shichusuimei_year_compare_prototype import compare_year
    source=yaml.safe_load(raw);b=source['systems']['shichusuimei']['normalized_data']['annual_forecasts']['items'][1]
    a=expand_shared_year(yaml.safe_load(addon),2027)
    rows=compare_year(source,b,a,'/base_year','/addon_year')
    assert {r['category'] for r in rows}=={'same_meaning','base_only','addon_only','comparison_pending'}
    for key,doc,prefix in [('base_paths',b,'/base_year'),('addon_paths',a,'/addon_year')]:
        from services.shichusuimei_full_prototype import pointer
        paths={prefix+pointer(p) for p,v in walk(doc) if not isinstance(v,(dict,list)) or not v}
        assert paths <= {p for r in rows for p in r[key]}
    assert any('reference' in r['fact'] or 'five_elements' in r['fact'] for r in rows if r['category']=='comparison_pending')


def test_missing_daiun_context_outside_base_forecast_range_is_rejected(raw,addon):
    doc=yaml.safe_load(addon);item=next(x for x in doc['systems']['shichusuimei']['annual_details']['years'] if x['selected_year']==2036)
    item['daiun']['contexts']=[]
    with pytest.raises(ExtractionError):extract_annual(raw,dump_extraction(doc),[2036])
