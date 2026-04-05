import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { VisitType } from "../../types";
import DisclaimerModal from "../common/DisclaimerModal";
import * as conversationService from "../../services/conversations";
import type { ConversationState } from "../../services/conversations";

type Step =
  | "disclaimer"
  | "visit_type"
  | "initial_concern"
  | "conversation"
  | "review"
  | "completed";

const MAX_QUESTIONS = 10;

export default function IntakeFlow() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("disclaimer");
  const [visitType, setVisitType] = useState<VisitType | null>(null);
  const [session, setSession] = useState<ConversationState | null>(null);
  const [answer, setAnswer] = useState("");
  const [initialConcern, setInitialConcern] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCheck, setShowCheck] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // ── Disclaimer ──
  const handleDisclaimerAccept = () => setStep("visit_type");
  const handleDisclaimerDecline = () => navigate("/");

  // ── Visit type selection ──
  const handleVisitTypeSelect = async (type: VisitType) => {
    setVisitType(type);
    if (type === "yearly_checkup") {
      await startSession(type);
    } else {
      setStep("initial_concern");
    }
  };

  // ── Start the conversation session ──
  const startSession = async (type: VisitType) => {
    setLoading(true);
    setError(null);
    try {
      const s = await conversationService.startConversation(type, true);
      setSession(s);
      setStep("conversation");
    } catch {
      setError("Failed to start the intake session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Submit the initial concern then start conversation ──
  const handleInitialConcernSubmit = async () => {
    if (!visitType || !initialConcern.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const s = await conversationService.startConversation(visitType, true);
      const updated = await conversationService.submitAnswer(s.id, initialConcern.trim());
      setSession(updated);
      setStep("conversation");
    } catch {
      setError("Failed to start the intake session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Submit an answer to the current question ──
  const handleSubmitAnswer = async () => {
    if (!session || !answer.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await conversationService.submitAnswer(session.id, answer.trim());
      setSession(updated);
      setAnswer("");
    } catch {
      setError("Failed to submit your answer. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Voice recording ──
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());

        if (session) {
          setLoading(true);
          try {
            await conversationService.uploadVoiceNote(session.id, blob);
          } catch {
            setError("Failed to upload voice note.");
          } finally {
            setLoading(false);
          }
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch {
      setError("Could not access microphone. Please check permissions.");
    }
  }, [session]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  // ── Complete ──
  const handleComplete = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      await conversationService.completeConversation(session.id);
      setStep("completed");
    } catch {
      setError("Failed to complete the session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Animate the checkmark after entering "completed" step
  useEffect(() => {
    if (step === "completed") {
      const timer = setTimeout(() => setShowCheck(true), 100);
      return () => clearTimeout(timer);
    }
  }, [step]);

  // ── Helpers ──
  const latestAiMessage = session?.messages
    .filter((m) => m.role === "ai")
    .slice(-1)[0];

  const questionProgress = session
    ? `${session.questions_asked_count} / ${MAX_QUESTIONS}`
    : "";

  // ── Completed view ──
  if (step === "completed") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center pt-16">
        {/* Animated checkmark circle */}
        <div
          className={`flex h-28 w-28 items-center justify-center rounded-full transition-all duration-700 ease-out ${
            showCheck
              ? "scale-100 bg-emerald-500 opacity-100"
              : "scale-50 bg-emerald-300 opacity-0"
          }`}
        >
          <svg
            className={`h-14 w-14 text-white transition-all duration-500 delay-300 ${
              showCheck ? "scale-100 opacity-100" : "scale-0 opacity-0"
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={3}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        {/* Title */}
        <h1
          className={`mt-8 text-2xl font-bold text-gray-900 transition-all duration-500 delay-500 ${
            showCheck ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
        >
          Intake Complete!
        </h1>

        {/* Subtitle */}
        <p
          className={`mt-3 text-center text-gray-500 transition-all duration-500 delay-700 ${
            showCheck ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
        >
          Your responses have been securely recorded and will help your
          physician prepare for your appointment.
        </p>

        {/* Info cards */}
        <div
          className={`mt-8 w-full space-y-3 transition-all duration-500 delay-[900ms] ${
            showCheck ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
        >
          <div className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-100">
              <svg className="h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-900">AI Report Generating</div>
              <div className="text-xs text-gray-500">
                Our AI is analyzing your responses to create a summary for your physician.
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100">
              <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-900">HIPAA Secured</div>
              <div className="text-xs text-gray-500">
                All your health information is encrypted end-to-end and stored securely.
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-purple-100">
              <svg className="h-5 w-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-900">Next Steps</div>
              <div className="text-xs text-gray-500">
                A scheduler will contact you to confirm your appointment time based on the AI's duration estimate.
              </div>
            </div>
          </div>
        </div>

        {/* Back to dashboard */}
        <button
          onClick={() => navigate("/")}
          className={`mt-8 rounded-xl bg-blue-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-200 hover:bg-blue-700 transition-all duration-500 delay-[1100ms] ${
            showCheck ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Intake Progress</span>
          {session && <span>Question {questionProgress}</span>}
        </div>
        <div className="mt-1 h-2 w-full rounded-full bg-gray-200">
          <div
            className="h-2 rounded-full bg-blue-500 transition-all"
            style={{
              width: session
                ? `${(session.questions_asked_count / MAX_QUESTIONS) * 100}%`
                : step === "disclaimer"
                  ? "0%"
                  : step === "visit_type"
                    ? "10%"
                    : "15%",
            }}
          />
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ── Step: Disclaimer ── */}
      <DisclaimerModal
        open={step === "disclaimer"}
        onAccept={handleDisclaimerAccept}
        onDecline={handleDisclaimerDecline}
      />

      {/* ── Step: Visit Type ── */}
      {step === "visit_type" && (
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-900">
            What type of visit would you like?
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Select the option that best describes your reason for scheduling.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <button
              onClick={() => handleVisitTypeSelect("yearly_checkup")}
              disabled={loading}
              className="group rounded-xl border-2 border-gray-200 p-6 text-left transition-colors hover:border-blue-500 hover:bg-blue-50"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 text-green-700 group-hover:bg-green-200">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="mt-3 font-semibold text-gray-900">Yearly Checkup</h3>
              <p className="mt-1 text-sm text-gray-500">
                Routine annual physical exam and wellness screening.
              </p>
            </button>

            <button
              onClick={() => handleVisitTypeSelect("specific_concern")}
              disabled={loading}
              className="group rounded-xl border-2 border-gray-200 p-6 text-left transition-colors hover:border-blue-500 hover:bg-blue-50"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 text-blue-700 group-hover:bg-blue-200">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              </div>
              <h3 className="mt-3 font-semibold text-gray-900">Specific Concern</h3>
              <p className="mt-1 text-sm text-gray-500">
                I have a particular symptom, condition, or health concern.
              </p>
            </button>
          </div>
        </div>
      )}

      {/* ── Step: Initial Concern ── */}
      {step === "initial_concern" && (
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-gray-900">
            Describe your concern
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Briefly tell us what is troubling you. You can type or use a voice
            note.
          </p>

          <textarea
            value={initialConcern}
            onChange={(e) => setInitialConcern(e.target.value)}
            placeholder="e.g., I've been having headaches for the past two weeks..."
            rows={4}
            className="mt-4 w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
          />

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={handleInitialConcernSubmit}
              disabled={loading || !initialConcern.trim()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Starting..." : "Continue"}
            </button>
            <span className="text-xs text-gray-400">or</span>
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors ${
                isRecording
                  ? "border-red-300 bg-red-50 text-red-700"
                  : "border-gray-300 text-gray-700 hover:bg-gray-50"
              }`}
            >
              <span className={`inline-block h-3 w-3 rounded-full ${isRecording ? "animate-pulse bg-red-500" : "bg-gray-400"}`} />
              {isRecording ? "Stop Recording" : "Voice Note"}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: Conversation ── */}
      {step === "conversation" && session && (
        <div className="space-y-4">
          {/* Messages history */}
          <div className="space-y-3">
            {session.messages.map((msg, idx) => (
              <div
                key={idx}
                className={`rounded-xl p-4 ${
                  msg.role === "ai"
                    ? "bg-white shadow-sm"
                    : msg.role === "patient"
                      ? "ml-8 bg-blue-50"
                      : "bg-gray-100 text-xs italic text-gray-500"
                }`}
              >
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
                  {msg.role === "ai" ? "Anilla" : msg.role === "patient" ? "You" : "System"}
                </div>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
          </div>

          {/* Answer input */}
          {session.status === "in_progress" && latestAiMessage && (
            <div className="rounded-xl bg-white p-4 shadow-sm">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmitAnswer()}
                  placeholder="Type your answer..."
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  autoFocus
                />
                <button
                  onClick={handleSubmitAnswer}
                  disabled={loading || !answer.trim()}
                  className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? "..." : "Send"}
                </button>
              </div>

              {/* Voice note option */}
              <div className="mt-3 flex justify-end">
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    isRecording
                      ? "bg-red-50 text-red-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  <span className={`inline-block h-2 w-2 rounded-full ${isRecording ? "animate-pulse bg-red-500" : "bg-gray-400"}`} />
                  {isRecording ? "Stop" : "Voice"}
                </button>
              </div>
            </div>
          )}

          {/* Complete button after some questions */}
          {session.status === "in_progress" && session.questions_asked_count >= 1 && (
            <div className="flex justify-end">
              <button
                onClick={() => setStep("review")}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Finish &amp; Review
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Step: Review ── */}
      {step === "review" && session && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-gray-900">
              Review Your Responses
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Please review all your responses before completing the intake.
            </p>

            <div className="mt-4 space-y-3">
              {session.messages
                .filter((m) => m.role !== "system")
                .map((msg, idx) => (
                  <div
                    key={idx}
                    className={`rounded-lg p-3 ${
                      msg.role === "ai" ? "bg-gray-50" : "ml-4 bg-blue-50"
                    }`}
                  >
                    <div className="text-xs font-medium uppercase text-gray-400">
                      {msg.role === "ai" ? "Question" : "Your Answer"}
                    </div>
                    <p className="mt-1 text-sm text-gray-800">{msg.content}</p>
                  </div>
                ))}
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <button
              onClick={() => setStep("conversation")}
              className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Go Back
            </button>
            <button
              onClick={handleComplete}
              disabled={loading}
              className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Completing..." : "Complete Intake"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
