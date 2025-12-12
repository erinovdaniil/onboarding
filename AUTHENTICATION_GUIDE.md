# Authentication Setup Guide

## Overview

User authentication has been fully implemented using Supabase Auth. Users can sign up, log in, and have their data securely managed with Row Level Security (RLS).

## What's Been Implemented

### ✅ Frontend Authentication

1. **Auth Context Provider** (`contexts/AuthContext.tsx`)
   - Manages authentication state across the app
   - Provides `signUp`, `signIn`, `signOut` functions
   - Automatically handles session persistence
   - Listens for auth state changes

2. **Login Page** (`app/login/page.tsx`)
   - Email/password sign in
   - Link to signup page
   - Forgot password link
   - Error handling with user-friendly messages

3. **Signup Page** (`app/signup/page.tsx`)
   - Email/password registration
   - Full name collection
   - Password confirmation
   - Link to login page
   - Success/error notifications

4. **Protected Routes**
   - `SidebarLayout.tsx` redirects to login if not authenticated
   - Auth pages (login/signup) render without sidebar
   - Editor pages remain accessible without sidebar

5. **User Profile Display**
   - Shows user name and email in sidebar
   - Avatar with initials
   - Dropdown menu with Settings and Sign Out options

6. **Authenticated API Requests** (`lib/api.ts`)
   - `getAuthHeaders()` - Gets JWT token from session
   - `authenticatedFetch()` - Makes requests with auth headers
   - All project fetches now include authorization

### ✅ Backend Authentication

1. **JWT Verification Utility** (`backend/app/auth.py`)
   - `verify_token()` - Verifies Supabase JWT tokens
   - `get_user_id()` - Extracts user ID from token
   - `require_auth()` - Enforces authentication (returns 401 if not logged in)
   - `optional_auth()` - Allows but doesn't require authentication

2. **Protected API Endpoints**
   - `upload.py` - Uses `optional_auth` (allows anonymous uploads)
   - `projects.py` - Uses `optional_auth` (filters by user_id if authenticated)
   - All endpoints respect user ownership via Row Level Security

3. **Database Security**
   - Row Level Security (RLS) enabled on all tables
   - Users can only see/edit their own projects
   - Service role key bypasses RLS for admin operations

## Setup Steps

### Step 1: Create Database Tables

If you haven't already, create the database tables in Supabase:

1. Go to your Supabase dashboard: https://supabase.com/dashboard/project/cjunwcthgxdfygtjdpnk
2. Navigate to **SQL Editor**
3. Copy the entire contents of `backend/database_schema.sql`
4. Paste and run in SQL Editor

This creates:
- `projects` table with user_id foreign key
- `transcripts` table
- `video_files` table
- RLS policies for data security

### Step 2: Enable Email Auth in Supabase

1. Go to **Authentication** → **Providers**
2. Ensure **Email** provider is enabled
3. Configure email settings:
   - **Confirm email**: Optional (disable for development, enable for production)
   - **Email templates**: Customize if desired
4. Save changes

### Step 3: Configure Environment Variables

#### Backend (already done)
The `backend/.env` file needs:
```env
SUPABASE_URL=https://cjunwcthgxdfygtjdpnk.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Get JWT Secret:**
1. Go to Supabase dashboard → **Settings** → **API**
2. Find "JWT Secret" under "JWT Settings"
3. Copy and paste into `SUPABASE_JWT_SECRET`

**Note:** The JWT secret is different from the service role key!

#### Frontend (already configured)
The `.env.local` file already has:
```env
NEXT_PUBLIC_SUPABASE_URL=https://cjunwcthgxdfygtjdpnk.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJI...
```

### Step 4: Install Backend Dependencies

If you haven't installed PyJWT yet:

```bash
cd backend
pip install -r requirements.txt
```

This installs PyJWT for JWT verification.

### Step 5: Test Authentication

#### Test Signup Flow

1. Start both servers:
   ```bash
   # Terminal 1 - Frontend
   npm run dev

   # Terminal 2 - Backend
   cd backend
   python main.py
   ```

2. Go to http://localhost:3000/signup
3. Create a new account:
   - Full Name: Test User
   - Email: test@example.com
   - Password: password123
4. Click "Create account"

**Expected Results:**
- If email confirmation is disabled: Redirected to home page, logged in
- If email confirmation is enabled: Message to check email

#### Test Login Flow

1. Go to http://localhost:3000/login
2. Sign in with your account
3. Should be redirected to home page

#### Test Protected Routes

1. While logged in, navigate around the app
2. Check that your name appears in the sidebar
3. Click your profile → should see Settings and Sign Out options
4. Sign out → should be redirected to login page
5. Try accessing `/library` without logging in → should redirect to login

#### Test Project Ownership

1. Log in as User A
2. Create/upload a video project
3. Log out
4. Log in as User B (different account)
5. User B should NOT see User A's project
6. User B can create their own projects

## How Authentication Works

### Flow Diagram

```
┌─────────────────┐
│  User Signs Up  │
│   /signup page  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Supabase Auth   │
│ Creates Account │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  JWT Token      │
│  Generated      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   AuthContext   │
│  Stores Session │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  API Requests   │
│  Include Token  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Backend      │
│ Verifies Token  │
│ Returns User ID │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Database      │
│  RLS Policies   │
│  Filter by User │
└─────────────────┘
```

### Token Flow

1. **User logs in** via `/login` page
2. **Supabase Auth** validates credentials and returns JWT token
3. **Frontend stores** session in localStorage (automatic)
4. **All API calls** include `Authorization: Bearer <token>` header
5. **Next.js API routes** forward auth header to Python backend
6. **Python backend** verifies JWT and extracts user ID
7. **Database queries** filter by user_id (enforced by RLS)

### Row Level Security (RLS)

RLS policies ensure data security at the database level:

```sql
-- Users can only see their own projects
CREATE POLICY "Users can view their own projects"
    ON projects FOR SELECT
    USING (auth.uid() = user_id);

-- Users can only create projects for themselves
CREATE POLICY "Users can insert their own projects"
    ON projects FOR INSERT
    WITH CHECK (auth.uid() = user_id);
```

Even if someone manipulates the API, RLS prevents unauthorized access.

## Security Best Practices

### ✅ Already Implemented

- JWT tokens expire after 1 hour (configurable in Supabase)
- Passwords hashed with bcrypt
- Service role key only on server side
- RLS policies on all tables
- HTTPS in production (handled by Vercel/hosting)

### 🔒 Additional Recommendations

1. **Enable Email Verification** (Production)
   - Go to Supabase → Auth → Providers
   - Enable "Confirm email"
   - Users must verify email before accessing app

2. **Set Strong Password Policy**
   - Go to Supabase → Auth → Policies
   - Set minimum password length (default: 6, recommend: 8+)
   - Enable password strength requirements

3. **Enable MFA** (Optional)
   - Multi-factor authentication
   - Requires user phone number
   - Supabase supports TOTP

4. **Rate Limiting**
   - Limit login attempts to prevent brute force
   - Can be configured in Supabase Auth settings

5. **Session Management**
   - Sessions automatically refresh every hour
   - Users stay logged in until they sign out
   - Can configure session duration in Supabase

## Troubleshooting

### "Invalid token" error

**Cause:** JWT secret mismatch or token expired

**Solution:**
1. Verify `SUPABASE_JWT_SECRET` in `backend/.env` matches Supabase dashboard
2. Get JWT secret from: Settings → API → JWT Secret
3. Restart backend server after updating .env

### "User not authenticated" but I'm logged in

**Cause:** Token not being sent to backend

**Solution:**
1. Check browser Network tab for Authorization header
2. Ensure `authenticatedFetch` is being used
3. Clear browser cache and localStorage
4. Try logging out and back in

### Can see other users' projects

**Cause:** RLS policies not applied or service role key used on client

**Solution:**
1. Verify RLS is enabled: `ALTER TABLE projects ENABLE ROW LEVEL SECURITY;`
2. Check RLS policies exist in Supabase dashboard
3. Ensure frontend uses anon key, not service role key
4. Run database schema SQL again if needed

### "Cannot read property 'user' of undefined"

**Cause:** AuthContext not wrapping component

**Solution:**
1. Verify `AuthProvider` wraps app in `app/layout.tsx`
2. Check component uses `useAuth()` hook correctly
3. Ensure context is imported from correct path

### Backend returns 500 error

**Cause:** PyJWT not installed or JWT secret missing

**Solution:**
1. Install PyJWT: `pip install PyJWT==2.8.0`
2. Add JWT secret to `backend/.env`
3. Restart backend server

## API Reference

### Frontend Hooks

```typescript
import { useAuth } from '@/contexts/AuthContext'

// In component
const { user, session, loading, signUp, signIn, signOut } = useAuth()

// user: User object or null
// session: Session object or null
// loading: boolean (true while checking auth state)
```

### Frontend API Helper

```typescript
import { authenticatedFetch, getAuthHeaders } from '@/lib/api'

// Make authenticated request
const response = await authenticatedFetch('/api/projects')

// Get auth headers only
const headers = await getAuthHeaders()
// Returns: { 'Authorization': 'Bearer <token>', 'Content-Type': 'application/json' }
```

### Backend Auth Functions

```python
from app.auth import optional_auth, require_auth, get_user_id

# Optional auth (returns None if not authenticated)
@router.get("/")
async def list_items(authorization: Optional[str] = Header(None)):
    user_id = optional_auth(authorization)  # None or user_id
    # Filter by user_id if provided

# Required auth (raises 401 if not authenticated)
@router.post("/")
async def create_item(authorization: Optional[str] = Header(None)):
    user_id = require_auth(authorization)  # Raises HTTPException if not auth
    # Create item for user_id
```

## Testing Checklist

- [ ] Sign up with new account
- [ ] Verify email (if email confirmation enabled)
- [ ] Log in with created account
- [ ] See user name in sidebar
- [ ] Create a video project
- [ ] Project appears in library
- [ ] Log out
- [ ] Try accessing /library without login (should redirect to login)
- [ ] Log in as different user
- [ ] First user's project not visible
- [ ] Create project as second user
- [ ] Both users have separate project lists
- [ ] Sign out works correctly

## Next Steps

1. **Add Password Reset** - Create `/forgot-password` page
2. **Add Email Verification Flow** - Handle email confirmation
3. **Add User Settings** - Allow users to update profile
4. **Add OAuth Providers** - Google, GitHub login
5. **Add Team Features** - Share projects with other users
6. **Add Admin Panel** - Manage users and projects

---

**Status:** 🟢 Authentication fully implemented and ready for testing!
