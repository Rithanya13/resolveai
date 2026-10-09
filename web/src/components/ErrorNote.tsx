export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <div className="callout callout-bad" role="alert">
      {error}
    </div>
  );
}
