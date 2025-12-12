import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://cjunwcthgxdfygtjdpnk.supabase.co'
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNqdW53Y3RoZ3hkZnlndGpkcG5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUxNTA0OTEsImV4cCI6MjA4MDcyNjQ5MX0.oaoPPK4fGVXE1vPQBk6rD-qGwkXq_VHQK9aDhBOcDMk'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Client-side Supabase client for browser usage
export const createSupabaseClient = () => {
  return createClient(supabaseUrl, supabaseAnonKey)
}

