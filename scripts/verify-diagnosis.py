import json

d=json.load(open('assistant/workflow.json'))
for n in d['conversation_flow']['nodes']:
    instr = n.get('instructions', '')
    if 'â' in instr or '\u2192' in instr or '\u2014' in instr:
        print(f"MOJIBAKE in {n['id']}")
        print(repr(instr[:100]))
    
print("Checking _cache_ttl_secs duplication...")
with open('functions/refill-webhook/function.py') as f:
    content = f.read()
    if content.count('self._cache_ttl_secs') > 1:
        print("WARNING: _cache_ttl_secs assigned multiple times")
