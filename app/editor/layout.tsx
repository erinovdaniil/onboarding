export default function EditorLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Editor pages don't use the sidebar layout - they have their own full-screen layout
  return <>{children}</>
}
