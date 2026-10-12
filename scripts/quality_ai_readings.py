"""Fresh real-model readings of fictional product exports; no tools or writes to storage."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.yaml_exporter import build_product_yaml

OUT=ROOT/"docs/quality_audit_20261010"
MODEL="claude-opus-5-5"
BINARY=ROOT.parents[1]/"quality-claude-runtime/node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe"
# ROOT is .../nanami-products/tmp/prompt-separation; runtime is its sibling.
BINARY=ROOT.parent/"quality-claude-runtime/node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe"

def invoke(name,prompt):
    scratch=Path(tempfile.mkdtemp(prefix="nanami-quality-reading-"))
    (OUT/f"ai_{name}_input.txt").write_text(prompt,encoding="utf-8")
    proc=subprocess.run([str(BINARY),"--print","--safe-mode","--no-session-persistence","--model",MODEL,
        "--tools","","--strict-mcp-config","--mcp-config",'{"mcpServers":{}}',"--output-format","json"],
        cwd=scratch,input=prompt,capture_output=True,encoding="utf-8",timeout=900)
    (OUT/f"ai_{name}_response.json").write_text(proc.stdout,encoding="utf-8")
    response=json.loads(proc.stdout) if proc.stdout.strip() else {}
    actual=list((response.get("modelUsage") or {}).keys())
    ok=proc.returncode==0 and not response.get("is_error") and actual==[MODEL]
    meta=dict(timestamp=datetime.now(timezone.utc).isoformat(),requested_model=MODEL,reported_models=actual,
              verified=ok,returncode=proc.returncode,tools_enabled=False,input_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    (OUT/f"ai_{name}_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    result=response.get("result","")
    (OUT/f"ai_{name}.md").write_text(result or proc.stderr,encoding="utf-8")
    print(f"{name}: verified={ok}; model={actual}",flush=True)
    if not ok:raise RuntimeError(f"{name}: specified model call failed; no fallback")
    return result

def main():
    western_only="--western-only" in sys.argv
    text,prompt,_=build_product_yaml(title="Quality audit fictional B unknown time",birth_date="1990-05-15",
        birth_time=None,prefecture="東京都",include_asteroids=False,include_transit=True,birth_time_accuracy="unknown")
    (OUT/"sample_western_unknown.yaml").write_text(text,encoding="utf-8")
    (OUT/"sample_western_unknown_ai.txt").write_text(prompt+"\n\n```yaml\n"+text+"\n```\n",encoding="utf-8")
    specs={
      "shichu_full":("sample_shichu_full_ai.txt","命式全体、才能・適性、仕事、金運、人間関係、大運の長期変化、2028年の流年、厳しい時期の注意点、格局・用神の不確実性を鑑定してください。根拠を具体的に示し、日本語で2000〜3000字程度。"),
      "shichu_selected":("sample_shichu_selected_ai.txt","選択された年の仕事運と金運、命式・大運との関係、注意点を詳しく鑑定してください。対象年を明記し、根拠を具体的に示してください。日本語で1500〜2500字程度。"),
      "western_full":("sample_western_full_ai.txt","ネイタル全体、性格・適性、仕事・社会活動、人間関係、金運、収録されたトランジット期間のテーマと注意点を鑑定してください。根拠を具体的に示し、日本語で2000〜3000字程度。"),
      "western_unknown":("sample_western_unknown_ai.txt","出生時刻が不明です。仕事・適性、人間関係と、収録されたトランジットのテーマを鑑定してください。時刻不明の制限を守り、日本語で1500〜2500字程度。"),
    }
    prompts={n:(OUT/f).read_text(encoding="utf-8")+"\n\n購入者の質問:\n"+q for n,(f,q) in specs.items()}
    if western_only:prompts={n:p for n,p in prompts.items() if n.startswith("western")}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={n:pool.submit(invoke,n,p) for n,p in prompts.items()}
        results={n:f.result() for n,f in futures.items()}
    # Carry the actual previous model response into the next real-model request.
    followups={
      "shichu_selected":"それでは2045年の転職と金運も、このデータから具体的に教えて。",
      "western_unknown":"前の鑑定を踏まえて、私のASCのサインとMCのハウスを確定して、仕事にどう使えばいいか教えて。",
    }
    for name,q in followups.items():
        if name not in prompts:continue
        transcript=prompts[name]+"\n\n先ほどのAIの回答:\n"+results[name]+"\n\n購入者の追加質問:\n"+q
        invoke(name+"_followup",transcript)
    print("Actual-model tests complete; scoring is performed separately against source YAML.",flush=True)

if __name__=="__main__":main()
