import { useCallback, useRef, useState } from "react";
import type { VisitType } from "../../types";
import DisclaimerModal from "../common/DisclaimerModal";
import * as conversationService from "../../services/conversations";
import type { ConversationState } from "../../services/conversations";

type Step =
  | "disclaimer"
  | "visit_type"
  | "initial_concern"
  | "conversation"
  | "review";

const MAX_QUESTIONS = 10;

export default function IntakeFlow() {
  const [step, setStep] = useState<Step>("disclaimer");
  const [visitType, setVisitType] = useState<VisitType | null>(null);
  const [session, setSession] = useState<ConversationState | null>(null);
  const [answer, setAnswer] = useState("");
  const [initialConcern, setInitialConcern] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // ── Disclaimer ──
  const handleDisclaimerAccept = () => setStep("visit_type");
  const handleDisclaimerDecline = () => {
    window.location.href = "/";
  };

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
      // Send the initial concern as the first answer
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
            // Voice note returns a transcript preview, not a full session update.
            // In production this would trigger a confirm-transcript step.
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
    try {
      await conversationService.completeConversation(session.id);
      window.location.href = "/";
    } catch {
      setError("Failed to complete the session.");
    } finally {
      setLoading(false);
    }
  };

  // ── Helpers ──
  const latestAiMessage = session?.messages
    .filter((m) => m.role === "ai")
    .slice(-1)[0];

  const questionProgress = session
    ? `${session.questions_asked_count} / ${MAX_QUESTIONS}`
    : "";

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
