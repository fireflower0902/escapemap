"""실제 수집기 설정에서 요청한 지점만 남기기. 테스트는 수집기의 동일 진입점을 사용."""
import copy

def select_cafes(module, cafe_ids):
    wanted=set(map(str,cafe_ids));found=set();selected={}
    for key in ('BRANCHES','SITES','BRANCH_MAP','SHOP_MAP','MERCHANT_MAP','LOCATION_MAP','THEMES','BRANDS'):
        value=getattr(module,key,None)
        if isinstance(value,list):
            if not any(isinstance(r,dict) and (r.get('cafe_id') or r.get('shop_map')) for r in value):continue
            chosen=[]
            for row in value:
                if not isinstance(row,dict):continue
                if str(row.get('cafe_id')) in wanted:chosen.append(row);found.add(str(row['cafe_id']))
                elif isinstance(row.get('shop_map'),dict):
                    shops={k:v for k,v in row['shop_map'].items() if str(v) in wanted}
                    if shops:entry=copy.deepcopy(row);entry['shop_map']=shops;chosen.append(entry);found.update(map(str,shops.values()))
            setattr(module,key,chosen);selected[key]=chosen
        elif isinstance(value,dict):
            if key=='THEMES':continue
            if not any((isinstance(r,dict) and r.get('cafe_id')) or isinstance(r,(str,int)) for r in value.values()):continue
            chosen={k:r for k,r in value.items() if str(r.get('cafe_id') if isinstance(r,dict) else r) in wanted}
            found.update(str(r.get('cafe_id') if isinstance(r,dict) else r) for r in chosen.values());setattr(module,key,chosen);selected[key]=[str(k) for k in chosen]
    if str(getattr(module,'CAFE_ID',None)) in wanted:found.add(str(module.CAFE_ID))
    if wanted-found:raise ValueError('선택한 카페가 크롤러 설정에 없습니다: '+str(sorted(wanted-found)))
    return selected
