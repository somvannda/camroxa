export function GET() {
  return Response.json({
    ok: true,
    service: "camxora.com",
    environment: process.env.NEXT_PUBLIC_CAMXORA_ENV ?? "development",
  });
}
