# Tutorial sample repo setup

This page contains the tiny buggy repository used by [Tutorial: build your first agent loop](tutorial-first-loop.md). The smaller the repo, the faster the demo.

---

## Create the repo

```bash
mkdir eden-tutorial && cd eden-tutorial
git init -q
cat > calc.py <<'EOF'
def add(a, b):
    return a - b   # wrong: should be a + b
EOF
cat > test_calc.py <<'EOF'
from calc import add

def test_add():
    assert add(2, 3) == 5
EOF
git add . && git commit -qm "initial buggy calc"
```

Sanity-check the bug exists:

```bash
python -m pytest test_calc.py
# 1 failed, 0 passed
```

Continue with [Install eden](tutorial-first-loop.md#2-install-eden).
