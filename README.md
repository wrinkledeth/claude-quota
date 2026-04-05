# Claude Quota CLI Tool

A simple wrapper for the cli command `claude /usage`

### Appearance 

![](image-1.png)

### Usage
```bash
# activate venv
pip install -r requirements.txt
python claude_quota.py
```

### Sample alias
```hbash
alias cq='cd /repo_dir/claude-quota && .venv/bin/python claude_quota.py'
```
### Note
If you run into claude asking if you turst the folder, just run claude first from within that directory and tell it to trust the folder.

