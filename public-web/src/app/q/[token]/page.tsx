import ScanPage from "./scan-page";

export const instant = false;

export default async function Page({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return <ScanPage key={token} token={token} />;
}
