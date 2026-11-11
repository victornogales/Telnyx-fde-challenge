import json, os, subprocess

print('=== Submission Checklist ===')
print()

# 1. README.md
with open('README.md') as f:
    readme = f.read()
print('[OK] README.md exists')
assert 'Try it' in readme
assert '+442045202115' in readme
assert 'Observability' in readme
assert 'Debugging story' in readme
print('[OK] README has phone number, observability, debugging story')

# 2. opencode.json
assert os.path.exists('opencode.json')
print('[OK] opencode.json exists')
with open('opencode.json') as f:
    oc = json.load(f)
assert '@telnyx/opencode' in oc.get('plugins', [])
print('[OK] opencode.json has @telnyx/opencode plugin')

# 3. DEMO_SCRIPT.md
assert os.path.exists('DEMO_SCRIPT.md')
print('[OK] DEMO_SCRIPT.md exists')

# 4. docs/architecture.md
with open('docs/architecture.md', encoding='utf-8') as f:
    arch = f.read()
assert 'Component Diagram' in arch
assert 'Primitive Choices' in arch
print('[OK] docs/architecture.md has diagrams and primitive table')

# 5. Workflow has expression edges
with open('assistant/workflow.json') as f:
    wf = json.load(f)
edges = [e for e in wf['conversation_flow']['edges'] if e.get('condition', {}).get('type') == 'expression']
print('OK  Workflow has %d expression edges:' % len(edges))
for e in edges:
    print('     - ' + e['id'])

# 6. Tag exists
result = subprocess.run(['git', 'tag', '-l', 'demo-day'], capture_output=True, text=True)
assert 'demo-day' in result.stdout
print('OK  git tag demo-day exists')

# 7. Check commit
result = subprocess.run(['git', 'rev-parse', 'demo-day'], capture_output=True, text=True)
tag_commit = result.stdout.strip()
result2 = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True)
head_commit = result2.stdout.strip()
assert tag_commit == head_commit
print('OK  demo-day tag points to HEAD (' + head_commit[:8] + ')')

print()
print('=== ALL SUBMISSION REQUIREMENTS MET ===')
