# Music Web — Daily Quota + Cambodia-Only + VPN Blocking

**Date:** 2026-08-15  
**Surfaces:** `platform_api`  
**Branch:** `feature/music-web-suno-create-shell`

## Summary

Critical security and business rule updates:
1. Changed quota from **lifetime** to **daily reset** (5 songs per day)
2. Added **per-IP daily limits** (5 songs per IP per day)
3. **Restricted access to Cambodia IPs only**
4. **Blocked all VPN and proxy connections**

## Changes

### 1. Daily Quota Reset (was: Lifetime)
**Problem**: Users had 5 songs forever - no recurring engagement  
**Solution**: Reset to 5 songs every day at midnight UTC

**Technical:**
- `_used_count()` now checks only today's date
- `_reserve_daily_slot()` checks daily usage, not lifetime sum
- SQL query updated to check `usage_date = today` instead of `SUM(all dates)`
- Error message: "Try again tomorrow or upgrade to Pro"

### 2. Per-IP Daily Limits
**Problem**: Users could create multiple accounts from same IP to bypass quota  
**Solution**: Enforce 5 songs per IP per day (same as per-user limit)

**Implementation:**
- Redis key: `abuse:ip_daily:{ip}:{YYYY-MM-DD}`
- Counter increments on each generation
- 24-hour TTL (auto-expires next day)
- Returns 429 error when IP hits 6th song

**Error response:**
```json
{
  "error_code": "IP_DAILY_LIMIT",
  "message": "Maximum 5 songs per day from one IP. Try again tomorrow."
}
```

### 3. Cambodia-Only Access
**Problem**: Service intended for Cambodia market only  
**Solution**: Geolocation check blocks non-Cambodia IPs

**Implementation:**
- Uses ip-api.com free API (45 req/min)
- Checks every generation request
- Blocks with 403 Forbidden if country_code != "KH"

**Error response:**
```json
{
  "error_code": "GEO_RESTRICTED",
  "message": "This service is only available in Cambodia."
}
```

**Allowed:**
- Cambodia IPs (country code: KH)

**Blocked:**
- All other countries (403 Forbidden)

### 4. VPN/Proxy Detection
**Problem**: Users can use VPNs to appear as Cambodia IPs  
**Solution**: Detect datacenter/VPN ASNs and block

**Detection method:**
- Checks ASN (Autonomous System Number) from IP lookup
- Blocks known VPN/proxy providers:
  - DigitalOcean, AWS, Google Cloud, Azure
  - Linode, Vultr, OVH, Hetzner
  - Any ASN containing "vpn", "proxy", "tor"

**Error response:**
```json
{
  "error_code": "VPN_DETECTED",
  "message": "VPN and proxy connections are not allowed. Please use a direct connection."
}
```

**What happens:**
- IP blocked for 1 hour
- Logged with ASN details

## Security Flow

```
Request → Cambodia IP? → VPN/Proxy? → Per-IP Limit? → Per-User Limit? → Generate
             ↓              ↓              ↓               ↓
           403 Block     403 Block      429 Block      429 Block
         (wrong country) (VPN detected) (IP maxed)    (user maxed)
```

## Business Rules

| Limit Type | Threshold | Reset | Enforcement |
|-----------|-----------|-------|-------------|
| Per-user | 5 songs/day | Daily 00:00 UTC | Database atomic |
| Per-IP | 5 songs/day | Daily 00:00 UTC | Redis counter |
| Geography | Cambodia only | Never | IP geolocation |
| VPN | Blocked | 1 hour | ASN detection |

## Error Codes

| Code | HTTP | Meaning | User Action |
|------|------|---------|-------------|
| `IP_DAILY_LIMIT` | 429 | IP used 5 songs today | Wait until tomorrow |
| `GEO_RESTRICTED` | 403 | Not in Cambodia | Use Cambodia IP |
| `VPN_DETECTED` | 403 | VPN/proxy detected | Disable VPN |
| `QUOTA_EXCEEDED` | 429 | User used 5 songs today | Wait or upgrade Pro |

## Files Modified

- `platform_api/services/web_music_service.py`
  - Changed `_used_count()` to check daily instead of lifetime
  - Updated `_reserve_daily_slot()` SQL to daily check
  - Updated error messages

- `platform_api/middleware/abuse_detection.py`
  - Added `check_ip_geolocation()` function
  - Added `is_vpn_or_proxy()` detection
  - Added per-IP daily counter
  - Added Cambodia-only restriction
  - Added VPN blocking

## Testing

### Daily Reset
1. Generate 5 songs → quota exhausted
2. Wait until next UTC day
3. Can generate 5 more songs

### Per-IP Limit
1. User A generates 3 songs (IP: X)
2. User B from same IP generates 2 songs (IP: X)
3. User A/B 3rd attempt → blocked (IP maxed at 5)

### Cambodia-Only
1. Test from Cambodia IP → works
2. Test from Thailand IP → 403 GEO_RESTRICTED
3. Test from USA IP → 403 GEO_RESTRICTED

### VPN Detection
1. Connect to Cambodia VPN → 403 VPN_DETECTED
2. Use DigitalOcean droplet → 403 VPN_DETECTED
3. Residential Cambodia ISP → works

## Monitoring

**Daily resets:**
```sql
-- Should reset to 0 each day
SELECT user_id, usage_date, generation_count
FROM web_music_daily_usage
WHERE usage_date = CURRENT_DATE;
```

**IP limits:**
```redis
KEYS abuse:ip_daily:*:2026-08-15
GET abuse:ip_daily:123.45.67.89:2026-08-15
```

**Geo blocks:**
```
WARNING: Blocked non-Cambodia IP {ip} (country: TH)
WARNING: Blocked VPN/proxy IP {ip} (ASN: digitalocean)
```

## Performance Impact

- **IP geolocation**: ~100-200ms per request (external API call)
- **Cached in Redis**: 5s TTL for config lookups
- **Daily query**: Single-row lookup, indexed on (user_id, usage_date)

## Migration / Deploy

No database migrations required (table already has usage_date column).

```bash
python3 scripts/deploy/sync_platform_api_sandbox.py
```

## Limitations

1. **IP geolocation accuracy**: ~95-98% for country-level
2. **VPN detection**: Not 100% - residential VPNs may slip through
3. **IP sharing**: Families/offices share IPs - may hit limit together
4. **API dependency**: ip-api.com must be available (has fallback)

## Follow-ups

- Consider paid IP database (MaxMind GeoIP2) for higher accuracy
- Add admin whitelist for specific IPs (testing, partners)
- Track blocked requests for abuse pattern analysis
- Consider captcha for repeated violations
