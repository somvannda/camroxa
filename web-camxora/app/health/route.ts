export function GET() {
  return Response.json({
    ok: true,
    service: "web-camxora",
    environment: process.env.NEXT_PUBLIC_CAMXORA_ENV ?? "development",
  });
}
