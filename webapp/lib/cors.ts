import { NextResponse } from "next/server";

// CORS aperto: questo server locale viene chiamato da un dominio diverso
// (il sito su Vercel) tramite tunnel, quindi il browser blocca la richiesta
// senza questi header. Va bene per un uso personale/di test, da restringere
// a un dominio specifico se il server resta esposto a lungo.
export function withCors(response: NextResponse): NextResponse {
  response.headers.set("Access-Control-Allow-Origin", "*");
  response.headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  response.headers.set("Access-Control-Allow-Headers", "Content-Type");
  return response;
}

export function corsPreflight(): NextResponse {
  return withCors(new NextResponse(null, { status: 204 }));
}
