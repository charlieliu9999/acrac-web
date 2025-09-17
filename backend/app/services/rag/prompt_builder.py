from typing import List, Dict, Optional


def build_candidates_block(candidates: Optional[List[Dict]]) -> str:
    if not candidates:
        return ""
    unique = []
    seen = set()
    for c in candidates:
        name = c.get('procedure_name_zh') or c.get('name_zh') or c.get('procedure_name') or ''
        modality = c.get('modality', '')
        key = (name, modality)
        if name and key not in seen:
            seen.add(key)
            unique.append({'name': name, 'modality': modality})
    if not unique:
        return ""
    lines = [f"{i+1}. {u['name']} ({u['modality']})" for i, u in enumerate(unique[:30])]
    return "\n候选检查（必须从下列候选中选择，不得输出候选之外的检查）：\n" + "\n".join(lines) + "\n"

