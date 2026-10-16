import csv
import json
from pathlib import Path
import pytest
from sql_schema_ai_exporter.model import Column, DbObject, from_records, load_file, normalize
from sql_schema_ai_exporter.exports import export_text, sql_ident
from sql_schema_ai_exporter.sqlserver import CATALOG_SQL, _braced

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "schema_sample.csv"


def test_csv_and_text_roundtrip(tmp_path):
    snap = load_file(SAMPLE)
    assert snap.database == 'SAMPLE_DB'
    assert len(snap.objects) == 4
    assert sum(map(lambda o: len(o.columns), snap.objects)) == 22
    sha = export_text(snap, tmp_path)
    assert len(sha) == 64
    snap2 = load_file(tmp_path / 'data' / 'schema_snapshot.json')
    assert snap.objects == snap2.objects
    with (tmp_path / 'data' / 'schema_columns.csv').open(encoding='utf-8-sig',newline='') as f:
        assert len(list(csv.DictReader(f))) == 22
    assert (tmp_path / 'docs' / 'schema_catalog.md').read_text(encoding='utf-8').count('| 1 |') == 4


def test_order_and_special_identifiers(tmp_path):
    s = normalize('Finance', [DbObject('d]bo','T','A B',(
        Column(2,'Amount [USD]'), Column(1,'中文 字段'), Column(3,'x|z'),))])
    assert [c.name for c in s.objects[0].columns] == ['中文 字段','Amount [USD]','x|z']
    export_text(s,tmp_path)
    md = (tmp_path/'docs'/'schema_catalog.md').read_text(encoding='utf-8')
    assert '[d]]bo]' in md
    assert '[x\\|z]' in md
    assert s.objects == load_file(tmp_path/'data'/'schema_snapshot.json').objects


def test_reject_duplicate_column_or_objects():
    with pytest.raises(ValueError, match='Duplicate ordinal'):
        normalize('X', [DbObject('dbo','T','T',(Column(1,'A'),Column(1,'B')))])
    with pytest.raises(ValueError, match='Duplicate object'):
        normalize('X', [DbObject('dbo','T','T',()), DbObject('dbo','T','t',())])


def test_zero_column_object_roundtrip(tmp_path):
    snap = from_records([{'database_name':'Z','schema_name':'dbo','object_type':'V','object_name':'Empty',
                          'column_ordinal':'','field_name':''}])
    export_text(snap,tmp_path)
    snap2=load_file(tmp_path/'data'/'schema_columns.csv')
    assert len(snap2.objects)==1 and snap2.objects[0].columns==()


def test_reject_mixed_db_and_bad_types():
    with pytest.raises(ValueError, match='multiple database'):
        from_records([{'database_name':'A','schema_name':'dbo','object_type':'T','object_name':'a'},
                      {'database_name':'B','schema_name':'dbo','object_type':'T','object_name':'b'}])
    with pytest.raises(ValueError, match='Invalid object type'):
        from_records([{'database_name':'A','schema_name':'dbo','object_type':'X','object_name':'a'}])


def test_sql_only_system_catalog():
    lower=CATALOG_SQL.lower()
    assert 'sys.objects' in lower and 'sys.columns' in lower and 'sys.schemas' in lower
    assert 'from sys.objects' in lower
    assert "o.type in ('u', 'v')" in lower
    assert _braced('a}b') == '{a}}b}'
