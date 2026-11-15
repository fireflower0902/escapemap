"""Sinbiweb 개편 공개 목록/시간표와 기존 단순 링크 형식을 함께 파싱."""
import re
from bs4 import BeautifulSoup

def parse_theme_list(html):
 result={}
 for a in BeautifulSoup(html,'html.parser').select('a[href]'):
  match=re.search(r"fun_theme_select\('([0-9]+)'",a['href'])
  if not match:continue
  title=a.select_one('.choice-themes__name, .theme_name, .theme-title')
  name=(title or a).get_text(' ',strip=True)
  if not name:continue
  duration=a.select_one('.choice-themes__playtime');m=re.search(r'(\d+)분',duration.get_text()) if duration else None
  result[match.group(1)]={'name':name,'duration_min':int(m.group(1)) if m else None}
 return result

def parse_time_list(html):
 result=[]
 for a in BeautifulSoup(html,'html.parser').select('a'):
  match=re.search(r'(?<!\d)((?:[012]\d):[0-5]\d)(?!\d)',a.get_text(' ',strip=True))
  if not match:continue
  css=set(a.get('class',[]))
  if css & {'disable','disabled','none','end'}:status='full'
  elif re.search(r'fun_theme_time_select\(',a.get('href','')):status='available'
  else:continue
  result.append({'time':match.group(1),'status':status})
 if len({r['time'] for r in result})!=len(result):raise ValueError('동일 테마에 중복된 시간대')
 return result
