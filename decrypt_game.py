import base64, json, struct, hashlib, sys

enc_b64 = "RCo9kIxenReuDsWCxGL1TUbZEzCB9Ebtu/jGrCJ+T+CN1EXjUcaCvtJlgtWdV975yTFTBPfFXXWRBHHeQ5dEJm20oKe64e/vDlK00OXWewkgzA9q85upOxUCGzV9P6Ih"
perm = [5, 2, 7, 0, 12, 1, 15, 8, 3, 10, 4, 14, 6, 9, 11, 13]

# Build inverse permutation
inv_perm = [0] * 16
for i, p in enumerate(perm):
    inv_perm[p] = i

def xorshift32(state):
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= (state >> 17) & 0xFFFFFFFF
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF

def try_decrypt(seed_val):
    if seed_val == 0:
        return None
    data = bytearray(base64.b64decode(enc_b64))
    # Step 1: Reverse XOR with xorshift32 keystream
    state = seed_val & 0xFFFFFFFF
    for i in range(0, len(data), 4):
        state = xorshift32(state)
        kb = struct.pack('<I', state)
        for j in range(4):
            if i + j < len(data):
                data[i + j] ^= kb[j]
    # Step 2: Reverse block permutation
    result = bytearray(len(data))
    for blk_start in range(0, len(data), 16):
        for i in range(16):
            src_idx = blk_start + inv_perm[i]
            dst_idx = blk_start + i
            if src_idx < len(data) and dst_idx < len(data):
                result[dst_idx] = data[src_idx]
    # Step 3: Remove PKCS#7 padding
    if len(result) == 0:
        return None
    pad_len = result[-1]
    if pad_len < 1 or pad_len > 16:
        return None
    if any(b != pad_len for b in result[-pad_len:]):
        return None
    plaintext = result[:-pad_len]
    # Step 4: Parse minified JSON
    try:
        text = plaintext.decode('utf-8')
        obj = json.loads(text)
        return obj
    except Exception:
        return None

# Generate candidate seeds from "OPENAI_API_KEY"
key_str = "OPENAI_API_KEY"
candidates = set()
kb = key_str.encode('utf-8')

# Direct byte interpretations
candidates.add(int.from_bytes(kb[:4], 'little'))
candidates.add(int.from_bytes(kb[:4], 'big'))
candidates.add(int.from_bytes(kb[-4:], 'little'))
candidates.add(int.from_bytes(kb[-4:], 'big'))

# Hash-based seeds
for h_func in [hashlib.md5, hashlib.sha1, hashlib.sha256]:
    h = h_func(key_str.encode()).digest()
    for offset in range(0, min(len(h), 16), 4):
        candidates.add(struct.unpack('<I', h[offset:offset+4])[0])
        candidates.add(struct.unpack('>I', h[offset:offset+4])[0])

# Sum-based seeds
s = sum(kb)
candidates.add(s)
candidates.add(s & 0xFFFFFFFF)
candidates.add((s * 0x9E3779B9) & 0xFFFFFFFF)

print(f"Testing {len(candidates)} candidate seeds...")
found = False
for seed in candidates:
    if seed == 0:
        continue
    result = try_decrypt(seed)
    if result is not None:
        print(f"SUCCESS with seed {seed} (0x{seed:08X})")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        found = True
        break

if not found:
    print("No candidate worked. Trying brute force 1..2^20...")
    for seed in range(1, 1 << 20):
        result = try_decrypt(seed)
        if result is not None:
            print(f"SUCCESS with seed {seed} (0x{seed:08X})")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            found = True
            break
    if not found:
        print("Brute force up to 2^20 also failed.")