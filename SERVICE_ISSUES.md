# Portofolio Service Issue Report

**Date**: 2026-08-28  
**Service**: portofolio.service  
**Current Status**: ❌ UNSTABLE (17 restarts)

---

## 🚨 Critical Issues Found

### Issue 1: Container Name Conflict
**Frequency**: Every restart  
**Error**:
```
docker: Error response from daemon: Conflict. 
The container name "/portofolio" is already in use by container "xxx".
```

**Root Cause**: 
- Systemd service `ExecStop` menghapus container dengan `docker rm`
- Tapi kadang gagal (container sudah tidak ada atau stuck)
- Saat restart, `docker run` gagal karena nama sudah terpakai

**Impact**: Service tidak bisa start dengan benar

---

### Issue 2: Jinja2 Template Error (Historical)
**Error**:
```
jinja2.exceptions.UndefinedError: 'content' is undefined
```

**Root Cause**:
- Template mengharapkan variable `content` (tunggal)
- Tapi code mengirim `contents` (jamak, untuk i18n)
- Ini sudah diperbaiki di commit sebelumnya

**Status**: ✅ ALREADY FIXED

---

### Issue 3: Stale Containers Accumulation
**Evidence**: Banyak container ID sampah di sistem
```
824dab75fa49   localhost/portofolio:latest   Up 10 minutes   portofolio
ed0482106ddb   f9a5d93ca2ef                  Created                              pensive_murdock
9470aa6bc079   583c887544ce                  Created                              pedantic_satoshi
... (15+ containers sampah)
```

**Impact**: 
- Memory leak
- Container name conflicts
- Systemd restart loop

---

## 📊 Restart Timeline

| Time | Event | Count |
|------|-------|-------|
| 18:14:08 | Failed (content undefined) | 10 |
| 18:14:18 | Failed (container conflict) | 11 |
| 18:14:28 | Failed (container conflict) | 12 |
| 18:36:13 | Failed (no such container) | 13 |
| 18:36:23 | Failed (container conflict) | 14 |
| 23:57:06 | Failed (no such container) | 15 |
| 23:57:16 | Failed (container conflict) | 16 |
| 23:58:14 | Failed (no such container) | 17 |
| 23:58:24 | **Started Successfully** | - |

**Current State**: Running since 23:58:24 (10 minutes ago)

---

## 🔧 Recommended Fixes

### Fix 1: Update Systemd Service (CRITICAL)
Change `ExecStop` to use `docker stop` + `docker rm -f`:

```ini
ExecStop=/usr/bin/docker stop -t 10 portofolio
ExecStopPost=/usr/bin/docker rm -f portofolio
```

### Fix 2: Add Container Cleanup (RECOMMENDED)
Add pre-start cleanup:
```ini
ExecStartPre=/usr/bin/docker rm -f portofolio 2>/dev/null || true
```

### Fix 3: Clean Up Orphaned Containers (IMMEDIATE)
```bash
docker rm -f $(docker ps -a | grep portofolio | awk '{print $1}')
docker system prune -f
```

---

## ✅ Current Status

- **Container**: Running (started 23:58:24)
- **Endpoints**: All responding (200 OK)
- **Resource endpoint**: Working
- **i18n system**: Working
- **Website**: Accessible via misbahwork.my.id

**Verdict**: Service is currently stable, but will crash again on next restart due to container management issues.

---

## 📝 Next Steps

1. **Immediate**: Run cleanup commands
2. **Short-term**: Update systemd service file
3. **Long-term**: Consider using docker-compose with proper restart policies
