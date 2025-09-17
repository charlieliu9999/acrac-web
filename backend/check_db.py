#!/usr/bin/env python3
import sys
sys.path.append('.')

from app.core.database import get_db
from app.models.acrac_models import Panel, Topic
from sqlalchemy.orm import Session

def main():
    try:
        db = next(get_db())
        panels = db.query(Panel).all()
        topics = db.query(Topic).all()
        
        print(f'科室数量: {len(panels)}')
        print(f'主题数量: {len(topics)}')
        
        print('\n前5个科室:')
        for p in panels[:5]:
            print(f'  {p.semantic_id}: {p.name_zh}')
        
        print('\n前5个主题:')
        for t in topics[:5]:
            print(f'  {t.semantic_id}: {t.name_zh} (科室: {t.panel_id})')
            
        db.close()
        
    except Exception as e:
        print(f'数据库连接错误: {e}')
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())