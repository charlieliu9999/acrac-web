-- Fix obvious modality mislabels for V/Q (SPECT) procedures
UPDATE procedure_dictionary
SET modality = 'Nuclear Medicine'
WHERE (name_zh ILIKE '%SPECT%' OR name_zh ILIKE '%V/Q%' OR name_en ILIKE '%V/Q%' OR name_en ILIKE '%Ventilation%' OR name_en ILIKE '%Perfusion%')
  AND (modality IS NULL OR modality ILIKE 'CT%');

-- Set pregnancy safety hints in clinical_recommendations based on procedure names
UPDATE clinical_recommendations cr
SET pregnancy_safety = '谨慎使用'
FROM procedure_dictionary pd
WHERE cr.procedure_id = pd.semantic_id
  AND pregnancy_safety IS NULL
  AND (pd.name_zh ILIKE '%CT肺动脉%' OR pd.name_en ILIKE '%CTA Pulmonary%');

UPDATE clinical_recommendations cr
SET pregnancy_safety = '安全'
FROM procedure_dictionary pd
WHERE cr.procedure_id = pd.semantic_id
  AND pregnancy_safety IS NULL
  AND (pd.name_zh ILIKE '%MRI%' OR pd.name_en ILIKE '%MRI%');

-- Backfill generic reasoning if missing for common PE workflows
UPDATE clinical_recommendations cr
SET reasoning_zh = '依据ACR/循证指南，结合临床验前概率与D-二聚体结果，选择CTPA或V/Q显像进行确证或排除。'
FROM procedure_dictionary pd
WHERE cr.procedure_id = pd.semantic_id
  AND cr.reasoning_zh IS NULL
  AND (pd.name_zh ILIKE '%CT肺动脉%' OR pd.name_zh ILIKE '%灌注%' OR pd.name_en ILIKE '%V/Q%' OR pd.name_en ILIKE '%CTA Pulmonary%');

-- Normalize DWI naming if present
UPDATE procedure_dictionary
SET name_zh = 'MR颅脑弥散加权成像(DWI)'
WHERE name_zh ILIKE '%弥散加权%'
  AND name_zh NOT ILIKE '%DWI%';

