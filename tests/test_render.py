import json
import subprocess
import sys
from pathlib import Path
from PIL import Image
import pytest
from sql_schema_ai_exporter.model import Column, DbObject, normalize, load_file
from sql_schema_ai_exporter.render import Config, lines_for_object, load_font, render, visual_ident
from sql_schema_ai_exporter.exports import export_text

SAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'schema_sample.csv'


def test_dense_png_and_mapping(tmp_path):
    snap=load_file(SAMPLE)
    config=Config(width=1100,height=1200,columns=2,font_size=18)
    report=render(snap,tmp_path/'images',config)
    assert report['status']=='PASS' and report['source_fields']==22
    assert report['images']>=1
    png=tmp_path/'images'/'schema_001.png'
    assert png.is_file()
    with Image.open(png) as image:
        assert image.size[0] == 1100 and image.size[1] <= 1200 and image.format=='PNG'
    assert (tmp_path/'images'/'image_manifest.csv').is_file()
    assert len(list((tmp_path/'images').glob('schema_*.png'))) == report['images']


def test_long_field_wraps_exactly():
    obj = DbObject('dbo','T','Big',(Column(1,'X'*240),Column(2,'Other')))
    font=load_font(19,None)
    result=lines_for_object(obj,font,220)
    assert len(result)>2
    # remove the continuation marker; the entire name is represented, untruncated.
    aggregate=''.join(x.text.removeprefix('↳') for x in result if 0 in x.indexes)
    assert aggregate=='X'*240
    assert any(x.text=='Other' for x in result)


def test_many_objects_multiple_pages_and_long_object_name(tmp_path):
    objs=[DbObject('dbo','T',('LongTableName_'+'Z'*75 if i==1 else f'Object_{i:02d}'),
          tuple(Column(j+1,'ExtremelyLongFieldName_'+'y'*20+f'_{j:02d}') for j in range(48)))
          for i in range(12)]
    snap=normalize('D',objs)
    report=render(snap,tmp_path,Config(width=900,height=950,columns=2,font_size=18))
    assert report['images']>1
    assert report['source_fields']==12*48
    assert report['layout_fields_covered']==12*48
    assert report['missing_fields']==0


def test_special_names_are_quoted():
    assert visual_ident('Name')=='Name'
    assert visual_ident('P&amp;L')=='[P&amp;L]'
    assert visual_ident('line\nname')=='[line\\nname]'


def test_bad_config():
    with pytest.raises(ValueError):
        Config(width=900,height=1200,columns=6,font_size=20)


def test_cli_end_to_end(tmp_path):
    cmd=[sys.executable,'-m','sql_schema_ai_exporter','--input',str(SAMPLE),
         '--out',str(tmp_path/'out'),'--width','1100','--height','1200',
         '--columns','2','--font-size','18']
    x=subprocess.run(cmd,text=True,capture_output=True)
    assert x.returncode == 0, x.stderr
    r=json.loads((tmp_path/'out'/'export_report.json').read_text(encoding='utf-8'))
    assert r['status']=='PASS' and r['source_fields']==22 and len(r['snapshot_sha256'])==64


def test_empty_view_appears_in_manifest(tmp_path):
    snap=normalize('X',[DbObject('dbo','V','Empty',())])
    r=render(snap,tmp_path,Config(width=1000,height=1000,columns=2,font_size=18))
    assert r['objects']==1 and r['source_fields']==0
    assert 'Empty' in (tmp_path/'image_manifest.csv').read_text(encoding='utf-8-sig')
