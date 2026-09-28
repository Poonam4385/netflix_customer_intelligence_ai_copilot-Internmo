from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(module,*args):
    cmd=[sys.executable,"-m",module,*args]
    print("\n>"," ".join(cmd))
    subprocess.run(cmd,cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fast",action="store_true",help="faster churn validation")
    p.add_argument("--rag",action="store_true",help="also build the vector index")
    a=p.parse_args()
    run("src.data_processing.clean_data")
    run("src.features.build_features")
    run("src.models.train_churn",*(["--fast"] if a.fast else []))
    run("src.models.train_segmentation")
    run("src.models.train_clv")
    run("src.services.retention")
    if a.rag: run("src.llm.rag")
    print("\nBootstrap complete.")

if __name__=="__main__": main()
