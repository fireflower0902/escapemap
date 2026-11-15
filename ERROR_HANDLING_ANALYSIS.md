# Error Handling Consistency Analysis: Invalid Area Parameters

## Executive Summary

**Critical Issue Found**: Frontend and backend have **inconsistent area validation** that creates a confusing user experience when selecting "konkuk" (건대/광진).

- **Backend**: Supports 9 Seoul areas (including "konkuk") with strict validation via `_validate_area()`
- **Frontend (Next.js Route Handler)**: Only recognizes 15 areas (missing "konkuk") - silently skips filtering
- **Frontend (Search Page)**: Offers 9 areas in dropdown including "konkuk"
- **Result**: User selects "konkuk" → confusing behavior where the area filtering is silently ignored

---

## File Inventory

| File | Role | Validation | Area Count |
|------|------|-----------|-----------|
| `backend/app/api/v1/cafes.py` | FastAPI endpoint | Strict (raises HTTPException 400) | 9 areas (line 18-21) |
| `frontend/app/api/search/route.ts` | Next.js Route Handler | Loose (silently skips) | 15 areas (line 20-24) |
| `frontend/app/search/page.tsx` | Search page UI | None (displays options) | 9 areas (line 11-21) |
| `frontend/components/SearchBar.tsx` | Search bar component | None (displays options) | 9 areas (line 8-18) |
| `backend/app/firestore_db.py` | Config | Reference data | 9 areas (line 29-39) |

---

## Question-by-Question Analysis

### 1. What happens when user selects "konkuk" and searches?

**Step-by-step flow:**

```
User selects "konkuk" from dropdown (search page line 15)
         ↓
Form submits with ?date=2026-06-13&area=konkuk
         ↓
Frontend fetch: /api/search?date=...&area=konkuk (line 168)
         ↓
Next.js Route Handler (route.ts:38): area = "konkuk"
         ↓
Line 45 check: VALID_AREAS.has("konkuk") → FALSE ❌
  - "konkuk" is NOT in VALID_AREAS (line 20-24)
  - Missing from the 15-area set
         ↓
Line 45-46: if condition FALSE, cafesQuery WITHOUT area filter
         ↓
Returns ALL active cafes from Firestore (not filtered by area!)
         ↓
User sees cafes from all areas, not just "konkuk" 👎
```

**Backend alternate path (if user hit /api/v1/search directly):**

```
User calls /api/v1/search?area=konkuk (FastAPI endpoint, line 116-204)
         ↓
Line 133: cafes = _get_cafes_sync(db, "konkuk")
         ↓
Line 40: validated_area = _validate_area("konkuk")
         ↓
Line 30: "konkuk" in SEOUL_AREAS → TRUE ✅
  (SEOUL_AREAS includes "konkuk", line 19)
         ↓
Returns cafes filtered by area="konkuk" ✅
         ↓
Works correctly!
```

**Problem**: Frontend Route Handler ≠ Backend API. Users route through Next.js, so they hit the buggy code path.

---

### 2. Error Handling in `get_cafes()` endpoint (line 100-113)

**Code:**
```python
@router.get("/cafes")
async def get_cafes(
    area: str | None = Query(None, description="지역 코드 (예: gangnam, hongdae, busan)"),
):
    db = get_db()
    cafes = await asyncio.to_thread(_get_cafes_sync, db, area)
    return {"cafes": cafes, "total": len(cafes), "area": area}
```

**Error Handling: YES ✅**

- Line 40: `_validate_area(area)` is called inside `_get_cafes_sync()`
- Line 31-34: HTTPException(400) is raised with user-friendly message
- FastAPI automatically propagates HTTPException to HTTP response
- Returns: `{"detail": "현재 서울 지역만 지원합니다. 지원 지역: ..."}`

**However**: This endpoint is **not used by the frontend**. The frontend uses its own Next.js Route Handler that bypasses this validation.

---

### 3. Error Message Quality

**Backend Error Message (FastAPI):**
```
"현재 서울 지역만 지원합니다. 지원 지역: daehakro, gangnam, hongdae, itaewon, jamsil, myeongdong, sinchon, sinlim, konkuk"
```

**Assessment:**
- ✅ Clear purpose: explains Seoul-only support
- ✅ Lists all valid areas
- ✅ Helpful and user-friendly
- ⚠️ Only shown when hitting FastAPI endpoint directly (users don't)

**Frontend Error Message:**
- ❌ No error message at all
- ❌ Silent failure: confusing "all areas" returned instead of "konkuk"
- ❌ User thinks area filtering is working but it's not

---

### 4. `/search` Endpoint Error Handling (line 116-204)

**Code:**
```python
@router.get("/search")
async def search(
    date: Date = Query(..., description="조회 날짜 (YYYY-MM-DD)"),
    area: str | None = Query(None, description="지역 코드"),
):
    db = get_db()
    ...
    def _query():
        cafes = _get_cafes_sync(db, area)  # Line 133
        ...
```

**Error Handling: YES ✅**

- Line 133: Calls `_get_cafes_sync()` which calls `_validate_area()`
- If invalid area → HTTPException(400) propagates
- Same error message as `/cafes` endpoint

**Same Problem**: Frontend doesn't call this endpoint either. The Next.js Route Handler is used instead.

---

### 5. Race Conditions & Versioning Issues

**Scenario**: Backend adds new area, frontend isn't deployed

**Impact Analysis:**

| Backend Change | Frontend Behavior | User Impact |
|---|---|---|
| Adds `incheon` to SEOUL_AREAS | Next.js VALID_AREAS doesn't have `incheon` | Silent filtering off; see all areas instead of Incheon |
| Updates error message | Frontend doesn't show error messages | No visible impact |
| Removes `konkuk` from backend | Next.js still allows `konkuk` in dropdown | 404 or empty results from backend |

**Risk Level: HIGH**

- **Frontend Route Handler (route.ts) hardcodes area list** → can drift from backend
- **Search Page AREAS list is separate** → another copy to keep in sync
- **SearchBar AREAS is yet another copy** → 3 places to update!
- **Multiple lists = multiple sync points = bugs**

---

## Root Cause: Area Lists Scattered Across Codebase

### Current State (2026-06-13)

```
backend/app/api/v1/cafes.py (line 18-21)
  SEOUL_AREAS = {"gangnam", "hongdae", "sinchon", "konkuk", "jamsil",
                 "itaewon", "myeongdong", "daehakro", "sinlim"}

frontend/app/api/search/route.ts (line 20-24)
  VALID_AREAS = {"gangnam", "hongdae", "sinchon", "jamsil", "itaewon",
                 "myeongdong", "daehakro", "sinlim", "busan", "daegu",
                 "gwangju", "daejeon", "incheon", "gyeonggi", "gangwon"}
  ❌ Missing "konkuk"!

frontend/app/search/page.tsx (line 11-21)
  AREAS = [
    { value: "gangnam", ... },
    { value: "hongdae", ... },
    { value: "sinchon", ... },
    { value: "konkuk", ... },     ← UI shows this
    ...
  ]

frontend/components/SearchBar.tsx (line 8-18)
  AREAS = [same as above]
```

### Discrepancies

| Area | Backend | Frontend Route | Frontend UI | Result |
|------|---------|---|---|---|
| konkuk | ✅ yes | ❌ no | ✅ yes | UI allows selection but API silently ignores it |
| busan | ❌ no | ✅ yes | ❌ no | Route allows it but UI doesn't offer it |
| daegu, gwangju, etc | ❌ no | ✅ yes | ❌ no | Route allows them but UI doesn't |

---

## Impact Assessment

### Users Affected

**By using `/api/search` route (Next.js handler):**
- ✅ Selecting any Seoul area works fine
- ❌ **Selecting "konkuk" returns all cafes instead of just konkuk cafes**
- ❌ No error message shown
- ❌ Silent filtering failure = confusing UX

### By hitting `/api/v1/search` directly (FastAPI backend):
- ✅ All validation works
- ✅ Clear error messages
- ✅ No one does this in production

---

## Recommended Fixes (Priority Order)

### HIGH PRIORITY: Fix the "konkuk" bug

**Option A: Add "konkuk" to Frontend VALID_AREAS (Quick fix)**
```typescript
// frontend/app/api/search/route.ts line 20-24
const VALID_AREAS = new Set([
  "gangnam", "hongdae", "sinchon", "konkuk",  // ← ADD THIS
  "jamsil", "itaewon", "myeongdong", "daehakro", "sinlim",
  // ... rest
]);
```
- ✅ Fixes konkuk immediately
- ✅ Minimal change
- ❌ Doesn't solve root cause (scattered lists)

**Option B: Centralize area configuration (Proper fix)**
1. Create `/frontend/lib/areas.ts`:
   ```typescript
   export const SEOUL_AREAS = [
     "gangnam", "hongdae", "sinchon", "konkuk", "jamsil",
     "itaewon", "myeongdong", "daehakro", "sinlim",
   ];
   export const REGIONAL_AREAS = [
     "busan", "daegu", "gwangju", "daejeon", "incheon", "gyeonggi", "gangwon",
   ];
   export const ALL_AREAS = [...SEOUL_AREAS, ...REGIONAL_AREAS];
   ```

2. Update all three places:
   ```typescript
   // frontend/app/api/search/route.ts
   const VALID_AREAS = new Set(ALL_AREAS);
   
   // frontend/app/search/page.tsx
   const AREAS = SEOUL_AREAS.map(v => ({ value: v, label: ... }));
   
   // frontend/components/SearchBar.tsx
   const AREAS = SEOUL_AREAS.map(v => ({ value: v, label: ... }));
   ```

3. (Future) Fetch area list from backend instead of hardcoding

### MEDIUM PRIORITY: Add error handling to frontend

```typescript
// frontend/app/api/search/route.ts
// Add validation with helpful error
if (area && !VALID_AREAS.has(area)) {
  return NextResponse.json(
    { error: `Unsupported area: ${area}. Supported areas: ${[...VALID_AREAS].join(", ")}` },
    { status: 400 }
  );
}
```

Then handle in page.tsx:
```typescript
.catch((err) => {
  console.error(err);
  if (err.status === 400) {
    setError(err.message || "Invalid search parameters");
  } else {
    setError("데이터를 불러오지 못했습니다...");
  }
})
```

### LOW PRIORITY: Backend-Frontend contract

Consider adding `/api/v1/areas` endpoint to return canonical area list:
```python
# backend/app/api/v1/cafes.py
@router.get("/areas")
async def get_supported_areas():
    """Returns all supported areas for this region."""
    return {
        "seoul_areas": list(SEOUL_AREAS),
        "regional_areas": [...],  # Add if backend expands
    }
```

Frontend can fetch this at startup or build time for validation.

---

## Testing Checklist

- [ ] Search for "konkuk" area → returns only konkuk cafes, not all
- [ ] Search for invalid area via frontend → shows error message
- [ ] Search for invalid area via direct API call → shows helpful error
- [ ] Compare Frontend UI areas vs Backend SEOUL_AREAS → exact match
- [ ] Compare area lists in search/page.tsx vs SearchBar.tsx → identical
- [ ] Check multiple deployments don't drift → centralized source

---

## Summary Table

| Aspect | Status | Issue |
|--------|--------|-------|
| **Backend validation** | ✅ Working | None |
| **Backend error messages** | ✅ Good | Only seen if hitting /api/v1 directly |
| **Frontend Route Handler validation** | ❌ Broken | Missing "konkuk", silently fails |
| **Frontend Route Handler errors** | ❌ Missing | No error message shown |
| **Frontend UI area list** | ✅ Complete | Includes "konkuk" |
| **Sync between lists** | ❌ Broken | 3 different lists, 2 hardcoded sets |
| **User-facing error clarity** | ❌ Poor | No feedback on invalid area selection |
| **Race condition risk** | ⚠️ High | Will happen when backend adds new area |

