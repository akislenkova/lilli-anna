/**
 * Epic SMART on FHIR OAuth callback page.
 *
 * Epic redirects here after the patient authorises Anilla to read their
 * health records.  The URL will contain either:
 *   ?code=<auth_code>&state=<state>   — success
 *   ?error=<code>&error_description=<msg>  — user denied or Epic error
 *
 * This page exchanges the code for tokens via the backend, then
 * navigates to /my-record.
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { connectEpic } from "../services/epic";

type Phase = "connecting" | "error" | "success";

export function EpicCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>("connecting");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    const error = params.get("error");
    const errorDesc = params.get("error_description");

    if (error) {
      setErrorMsg(errorDesc ?? error);
      setPhase("error");
      return;
    }

    if (!code || !state) {
      setErrorMsg("Missing authorization code. Please try connecting again.");
      setPhase("error");
      return;
    }

    connectEpic({ code, state })
      .then(() => {
        setPhase("success");
        setTimeout(() => navigate("/my-record"), 1200);
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ??
          "Failed to connect your Epic account. Please try again.";
        setErrorMsg(msg);
        setPhase("error");
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-sm w-full text-center">
        {phase === "connecting" && (
          <>
            <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">
              Connecting your Epic account…
            </h2>
            <p className="mt-1 text-sm text-gray-500">This only takes a moment.</p>
          </>
        )}

        {phase === "success" && (
          <>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
              <svg className="h-6 w-6 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Connected!</h2>
            <p className="mt-1 text-sm text-gray-500">Redirecting to your health record…</p>
          </>
        )}

        {phase === "error" && (
          <>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
              <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Connection failed</h2>
            <p className="mt-1 text-sm text-gray-500">{errorMsg}</p>
            <button
              onClick={() => navigate("/my-record")}
              className="mt-6 rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
            >
              Back to my record
            </button>
          </>
        )}
      </div>
    </div>
  );
}
