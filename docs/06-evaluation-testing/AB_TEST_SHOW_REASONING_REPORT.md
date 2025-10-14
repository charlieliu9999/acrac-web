

## A/B报告 2025-09-27T18:02:13
- 数据源: `/Users/charlieliu/git_project_vscode/09_medical/ACRAC-web/ACR_data/影像测试样例-0318-1.xlsx` (n=10)
- 参数: top_scenarios=2, top_recs=3, sim_thres=0.6, with_ragas=False
- A 含理由: avg_ms=50968.3, prompt_len=2699.4, top1=20.0%, top3=30.0%
- B 不含理由: avg_ms=46130.6, prompt_len=1767.8, top1=20.0%, top3=30.0%
- 差值(A-B): Δms=4837.7, Δprompt=931.6, Δtop1=0.0%, Δtop3=0.0%
- 结论建议: 若不含理由方案 top1/top3 基本持平，且 avg_ms 与 prompt_len 显著下降，建议默认不带理由，并对评分并列/低相似度/高风险信号命中时再附简短理由。


## A/B报告 2025-09-27T19:48:20
- 数据源: `/Users/charlieliu/git_project_vscode/09_medical/ACRAC-web/ACR_data/影像测试样例-0318-1.xlsx` (n=50)
- 参数: top_scenarios=2, top_recs=3, sim_thres=0.6, with_ragas=False
- A 含理由: avg_ms=58878.24, prompt_len=2527.94, top1=10.0%, top3=12.0%
- B 不含理由: avg_ms=49049.66, prompt_len=1720.02, top1=12.0%, top3=16.0%
- 差值(A-B): Δms=9828.58, Δprompt=807.92, Δtop1=-2.0%, Δtop3=-4.0%
- 结论建议: 若不含理由方案 top1/top3 基本持平，且 avg_ms 与 prompt_len 显著下降，建议默认不带理由，并对评分并列/低相似度/高风险信号命中时再附简短理由。
