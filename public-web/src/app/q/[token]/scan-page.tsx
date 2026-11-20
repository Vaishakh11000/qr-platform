
"use client";

import Image from "next/image";
import ProductDetails from "../../../components/product-details";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

type LocationPayload = {
  location_status: "GPS" | "SKIPPED" | "DENIED" | "UNAVAILABLE";
  latitude?: number;
  longitude?: number;
  accuracy_meters?: number;
};

type ScanStart = {
  scan_id: string;
  location_requested: boolean;
  location_requirement: "MANDATORY" | "SKIPPABLE" | null;
  location_method: "GPS_REQUIRED" | "GPS_IP_FALLBACK" | "IP_ONLY" | null;
};

type Product = {
  id: string;
  version_id: string;
  version_number: number;
  sku: string;
  name: string;
  content_snapshot: Record<string, unknown>;
};

type Media = {
  id: string;
  media_type: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  display_order: number;
  alt_text: string | null;
};

type FormField = {
  key: string;
  label: string;
  type: "TEXT" | "EMAIL" | "PHONE" | "TEXTAREA" | "SELECT" | "CHECKBOX";
  required: boolean;
  options?: string[];
  max_length?: number;
};

type PublicForm = {
  id: string;
  form_id: string;
  name: string;
  description: string | null;
  version_number: number;
  requirement: "MANDATORY" | "OPTIONAL";
  schema: { fields: FormField[] };
};

type Completion = {
  scan_id: string;
  result_status: "ALLOWED" | "BLOCKED";
  location_status: string;
  message: string;
  product: Product | null;
};

type ViewState =
  | "loading"
  | "location"
  | "processing"
  | "blocked"
  | "error"
  | "product";

type LocationPermission = PermissionState | "unknown";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isScanStart(value: unknown): value is ScanStart {
  return isRecord(value)
    && typeof value.scan_id === "string"
    && value.scan_id.length > 0
    && typeof value.location_requested === "boolean"
    && (value.location_requirement === null || value.location_requirement === "MANDATORY" || value.location_requirement === "SKIPPABLE")
    && (value.location_method === null || value.location_method === "GPS_REQUIRED" || value.location_method === "GPS_IP_FALLBACK" || value.location_method === "IP_ONLY");
}

function isProduct(value: unknown): value is Product {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.version_id === "string"
    && typeof value.version_number === "number"
    && typeof value.sku === "string"
    && typeof value.name === "string"
    && isRecord(value.content_snapshot);
}

function isCompletion(value: unknown): value is Completion {
  return isRecord(value)
    && typeof value.scan_id === "string"
    && (value.result_status === "ALLOWED" || value.result_status === "BLOCKED")
    && typeof value.location_status === "string"
    && typeof value.message === "string"
    && (value.product === null || isProduct(value.product));
}

function isMediaList(value: unknown): value is Media[] {
  return Array.isArray(value) && value.every((item) => isRecord(item)
    && typeof item.id === "string"
    && typeof item.media_type === "string"
    && typeof item.original_filename === "string"
    && typeof item.mime_type === "string"
    && typeof item.file_size_bytes === "number"
    && typeof item.display_order === "number"
    && (item.alt_text === null || typeof item.alt_text === "string"));
}

function isFormField(value: unknown): value is FormField {
  return isRecord(value)
    && typeof value.key === "string"
    && typeof value.label === "string"
    && ["TEXT", "EMAIL", "PHONE", "TEXTAREA", "SELECT", "CHECKBOX"].includes(String(value.type))
    && typeof value.required === "boolean"
    && (value.options === undefined || (
      Array.isArray(value.options)
      && value.options.every((option) => typeof option === "string")
    ));
}

function isPublicFormList(value: unknown): value is PublicForm[] {
  return Array.isArray(value) && value.every((item) => isRecord(item)
    && typeof item.id === "string"
    && typeof item.form_id === "string"
    && typeof item.name === "string"
    && (item.description === null || typeof item.description === "string")
    && typeof item.version_number === "number"
    && (item.requirement === "MANDATORY" || item.requirement === "OPTIONAL")
    && isRecord(item.schema)
    && Array.isArray(item.schema.fields)
    && item.schema.fields.every(isFormField));
}

function isFormSubmission(value: unknown): value is { id: string; submitted_at: string } {
  return isRecord(value) && typeof value.id === "string" && typeof value.submitted_at === "string";
}

async function readResponse<T>(
  response: Response,
  fallback: string,
  validate: (body: unknown) => body is T,
): Promise<T> {
  let body: unknown;
  try { body = await response.json(); } catch { throw new Error(fallback); }
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body
      ? (body as { detail?: unknown }).detail : null;
    throw new Error(typeof detail === "string" ? detail : fallback);
  }
  if (!validate(body)) throw new Error(fallback);
  return body;
}

function displayValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function stringList(value: unknown): unknown[] {
  return Array.isArray(value) ? value.filter((item) => item != null && displayValue(item) !== "") : [];
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatFileType(media: Media): string {
  const extension = media.original_filename.split(".").pop();
  if (extension && extension !== media.original_filename) return extension.toUpperCase();
  return media.mime_type.split("/").pop()?.toUpperCase() || "FILE";
}

function officialProductLinks(value: unknown) {
  if (typeof value !== "string") return null;
  try {
    const source = new URL(value);
    if (source.protocol !== "https:" || source.username || source.password) return null;

    const hostname = source.hostname.toLowerCase();
    if (hostname === "vinsak.com" || hostname.endsWith(".vinsak.com")) {
      return {
        sourceUrl: source.toString(),
        contactUrl: "https://vinsak.com/contact-us/",
        contactName: "VINSAK",
      };
    }
    if (hostname === "rotatek.com" || hostname.endsWith(".rotatek.com")) {
      return {
        sourceUrl: source.toString(),
        contactUrl: "https://www.rotatek.com/contact-us/",
        contactName: "ROTATEK",
      };
    }
  } catch {
    return null;
  }
  return null;
}

export default function ScanPage({ token }: { token: string }) {
  const [view, setView] = useState<ViewState>("loading");
  const [message, setMessage] = useState("Verifying QR code...");
  const [scan, setScan] = useState<ScanStart | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [media, setMedia] = useState<Media[]>([]);
  const [forms, setForms] = useState<PublicForm[]>([]);
  const [formAnswers, setFormAnswers] = useState<Record<string, Record<string, string | boolean>>>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submittedForms, setSubmittedForms] = useState<Set<string>>(() => new Set());
  const [submittingFormId, setSubmittingFormId] = useState<string | null>(null);
  const [mediaLoading, setMediaLoading] = useState(false);
  const [mediaError, setMediaError] = useState("");
  const [failedMediaIds, setFailedMediaIds] = useState<Set<string>>(() => new Set());
  const [lightboxMediaId, setLightboxMediaId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [locationRequesting, setLocationRequesting] = useState(false);
  const [locationPermission, setLocationPermission] = useState<LocationPermission>("unknown");
  const [startAttempt, setStartAttempt] = useState(0);

  // Keep the scan ID independent of React's asynchronous state updates.
  const scanIdRef = useRef<string | null>(null);
  const operationGenerationRef = useRef(0);

  // Prevent duplicate location submissions.
  const submittingRef = useRef(false);
  const mountedRef = useRef(true);
  const locationAttemptRef = useRef(0);
  const lightboxRef = useRef<HTMLDivElement>(null);
  const lightboxCloseRef = useRef<HTMLButtonElement>(null);
  const lightboxReturnFocusRef = useRef<HTMLElement | null>(null);
  const lightboxImagesRef = useRef<Media[]>([]);
  const lightboxMediaIdRef = useRef<string | null>(null);
  const lightboxTouchStartXRef = useRef<number | null>(null);

  // Reuse the same start request during React Strict Mode effect replay.
  const startRequestRef = useRef<{
    token: string;
    promise: Promise<void>;
  } | null>(null);

  const submitLocation = useCallback(
    async (
      scanId: string,
      payload: LocationPayload,
    ) => {
      if (!mountedRef.current || submittingRef.current) return;

      const operationGeneration = operationGenerationRef.current;
      submittingRef.current = true;
      setBusy(true);
      setView("processing");
      setMessage("Verifying your request...");

      try {
        const response = await fetch(
          `/api/v1/public/scans/${encodeURIComponent(scanId)}/location`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          },
        );

        const result = await readResponse(response, "The scan could not be completed.", isCompletion);
        if (!mountedRef.current || operationGeneration !== operationGenerationRef.current) return;

        if (result.result_status !== "ALLOWED") {
          setView("blocked");
          setMessage(result.message);
          return;
        }

        if (!result.product) {
          throw new Error("Product information is unavailable.");
        }

        setProduct(result.product);
        setMessage(result.message);
        setView("product");

        setMediaLoading(true);
        setMediaError("");
        try {
          const mediaResponse = await fetch(
            `/api/v1/public/scans/${encodeURIComponent(result.scan_id)}/media`,
          );
          const mediaResult = await readResponse(mediaResponse, "Product media could not be loaded.", isMediaList);
          if (!mountedRef.current || operationGeneration !== operationGenerationRef.current) return;
          setMedia(mediaResult);
        } catch (error) {
          if (mountedRef.current && operationGeneration === operationGenerationRef.current) {
            setMediaError(error instanceof Error ? error.message : "Product media could not be loaded.");
          }
        } finally {
          if (mountedRef.current && operationGeneration === operationGenerationRef.current) setMediaLoading(false);
        }

        try {
          const formsResponse = await fetch(
            `/api/v1/public/scans/${encodeURIComponent(result.scan_id)}/forms`,
          );
          const publicForms = await readResponse(formsResponse, "Product forms could not be loaded.", isPublicFormList);
          if (mountedRef.current && operationGeneration === operationGenerationRef.current) setForms(publicForms);
        } catch (error) {
          if (mountedRef.current && operationGeneration === operationGenerationRef.current) setFormErrors({ _page: error instanceof Error ? error.message : "Product forms could not be loaded." });
        }
      } catch (error) {
        if (!mountedRef.current || operationGeneration !== operationGenerationRef.current) return;
        setView("error");
        setMessage(
          error instanceof Error
            ? error.message
            : "An unexpected error occurred.",
        );
      } finally {
        if (operationGeneration === operationGenerationRef.current) {
          submittingRef.current = false;
          if (mountedRef.current) setBusy(false);
        }
      }
    },
    [],
  );

  const requestLocation = useCallback(() => {
    const scanId = scanIdRef.current;

    if (!scanId || submittingRef.current) return;

    if (!navigator.geolocation) {
      setLocationRequesting(false);
      void submitLocation(scanId, {
        location_status: "UNAVAILABLE",
      });
      return;
    }

    const attempt = ++locationAttemptRef.current;
    setLocationRequesting(true);
    setView("location");
    setMessage("Waiting for location permission...");

    try {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (!mountedRef.current || attempt !== locationAttemptRef.current) return;
          setLocationRequesting(false);
          void submitLocation(scanId, {
            location_status: "GPS",
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_meters: position.coords.accuracy,
          });
        },
        (error) => {
          if (!mountedRef.current || attempt !== locationAttemptRef.current) return;
          setLocationRequesting(false);
          if (error.code === error.PERMISSION_DENIED) {
            setLocationPermission("denied");
          }
          void submitLocation(scanId, {
            location_status:
              error.code === error.PERMISSION_DENIED
                ? "DENIED"
                : "UNAVAILABLE",
          });
        },
        {
          enableHighAccuracy: true,
          timeout: 15000,
          maximumAge: 0,
        },
      );
    } catch {
      if (!mountedRef.current || attempt !== locationAttemptRef.current) return;
      setLocationRequesting(false);
      void submitLocation(scanId, { location_status: "UNAVAILABLE" });
    }
  }, [submitLocation]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!scan?.location_requested || !navigator.permissions?.query) {
      return;
    }

    let cancelled = false;
    let permissionStatus: PermissionStatus | null = null;
    const updatePermission = () => {
      if (!cancelled && permissionStatus) {
        setLocationPermission(permissionStatus.state);
      }
    };

    void navigator.permissions.query({ name: "geolocation" }).then((result) => {
      if (cancelled) return;
      permissionStatus = result;
      updatePermission();
      result.onchange = updatePermission;
    }).catch(() => {
      if (!cancelled) setLocationPermission("unknown");
    });

    return () => {
      cancelled = true;
      if (permissionStatus) permissionStatus.onchange = null;
    };
  }, [scan?.location_requested, scan?.scan_id]);

  useEffect(() => {
    // Reuse the in-flight request if Strict Mode replays this effect.
    if (startRequestRef.current?.token === token) {
      return;
    }

    const operationGeneration = ++operationGenerationRef.current;
    const promise = (async () => {
      try {
        const response = await fetch("/api/v1/public/scans/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

          const result = await readResponse(response, "This QR code could not be verified.", isScanStart);
        if (!mountedRef.current || operationGeneration !== operationGenerationRef.current) return;

        scanIdRef.current = result.scan_id;
        setScan(result);

        if (!result.location_requested) {
          setView("location");
          setMessage("Continue to view product information.");
          return;
        }

        if (result.location_method === "IP_ONLY") {
          await submitLocation(result.scan_id, {
            location_status: "UNAVAILABLE",
          });
          return;
        }

        setView("location");
        setMessage(
          result.location_requirement === "MANDATORY"
            ? "Location is required to access this product. Your location will be checked against its regional access policy."
            : "Location is optional. Sharing it helps verify where this product was accessed; you can continue without it.",
        );
      } catch (error) {
        if (!mountedRef.current || operationGeneration !== operationGenerationRef.current) return;
        setView("error");
        setMessage(
          error instanceof Error
            ? error.message
            : "Unable to start scan.",
        );
      }
    })();

    startRequestRef.current = { token, promise };
    void promise;
  }, [token, submitLocation, startAttempt]);

  const content = product?.content_snapshot ?? {};

  const title =
    stringValue(content.title) ||
    stringValue(content.name) ||
    product?.name ||
    "Product";

  const shortDescription = stringValue(content.short_description);
  const description = stringValue(content.description);
  const officialLinks = officialProductLinks(content.source_url);

  const features = stringList(content.features);
  const benefits = stringList(content.benefits);
  const applications = stringList(content.applications);
  const materials = stringList(content.supported_materials);
  const specifications =
    content.specifications &&
    typeof content.specifications === "object" &&
    !Array.isArray(content.specifications)
      ? (content.specifications as Record<string, unknown>)
      : {};
  const standardFields = new Set([
    "title", "name", "description", "short_description", "source_url", "features", "benefits",
    "applications", "supported_materials", "specifications",
  ]);
  const customFields = Object.entries(content).filter(([key, value]) =>
    !standardFields.has(key) && value != null && displayValue(value) !== "",
  );
  const hasProductDetails = Boolean(
    shortDescription || description || features.length || benefits.length || applications.length ||
    materials.length || Object.keys(specifications).length || customFields.length,
  );

  function markMediaFailed(mediaId: string) {
    setFailedMediaIds((previous) => new Set(previous).add(mediaId));
  }

  async function handleFormSubmit(event: FormEvent<HTMLFormElement>, form: PublicForm) {
    event.preventDefault();
    if (!scan?.scan_id || submittedForms.has(form.id)) return;
    const operationGeneration = operationGenerationRef.current;
    setSubmittingFormId(form.id);
    setFormErrors((current) => ({ ...current, [form.id]: "" }));
    try {
      const response = await fetch(
        `/api/v1/public/scans/${encodeURIComponent(scan.scan_id)}/forms/${encodeURIComponent(form.id)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answers: formAnswers[form.id] ?? {} }),
        },
      );
      await readResponse(response, "Your response could not be submitted.", isFormSubmission);
      if (operationGeneration !== operationGenerationRef.current) return;
      setSubmittedForms((current) => new Set(current).add(form.id));
    } catch (error) {
      if (operationGeneration !== operationGenerationRef.current) return;
      setFormErrors((current) => ({
        ...current,
        [form.id]: error instanceof Error ? error.message : "Your response could not be submitted.",
      }));
    } finally {
      if (operationGeneration === operationGenerationRef.current) setSubmittingFormId(null);
    }
  }

  const images = media.filter((item) => item.media_type === "IMAGE");
  const lightboxImages = images.filter((item) => !failedMediaIds.has(item.id));
  const galleryImages = images.slice(1).filter((item) => !failedMediaIds.has(item.id));
  const isLightboxOpen = lightboxMediaId !== null;
  const lightboxImage = lightboxImages.find((item) => item.id === lightboxMediaId);
  lightboxImagesRef.current = lightboxImages;
  lightboxMediaIdRef.current = lightboxMediaId;
  const videos = media.filter((item) => item.media_type === "VIDEO");
  const documents = media.filter((item) => item.media_type === "DOCUMENT");
  const unsupportedMedia = media.filter(
    (item) => !["IMAGE", "VIDEO", "DOCUMENT"].includes(item.media_type),
  );
  const accessStatusLabel: Record<ViewState, string> = {
    loading: "Verifying QR",
    location: "Location verification",
    processing: "Checking access",
    blocked: "Access restricted",
    error: "Not verified",
    product: "Verified product",
  };

  useEffect(() => {
    if (!isLightboxOpen) {
      if (lightboxReturnFocusRef.current?.isConnected) lightboxReturnFocusRef.current.focus();
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    lightboxCloseRef.current?.focus();
    function handleLightboxKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setLightboxMediaId(null);
        return;
      }
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        const currentImages = lightboxImagesRef.current;
        if (currentImages.length < 2) return;
        event.preventDefault();
        const currentIndex = currentImages.findIndex((item) => item.id === lightboxMediaIdRef.current);
        const step = event.key === "ArrowRight" ? 1 : -1;
        const nextIndex = (currentIndex + step + currentImages.length) % currentImages.length;
        setLightboxMediaId(currentImages[nextIndex].id);
        return;
      }
      if (event.key === "Tab") {
        const focusable = lightboxRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled)");
        if (!focusable?.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    window.addEventListener("keydown", handleLightboxKeyDown);
    return () => {
      window.removeEventListener("keydown", handleLightboxKeyDown);
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [isLightboxOpen]);

  function openLightbox(mediaId: string, trigger: HTMLElement) {
    lightboxReturnFocusRef.current = trigger;
    setLightboxMediaId(mediaId);
  }

  function moveLightbox(direction: -1 | 1) {
    const currentImages = lightboxImagesRef.current;
    if (currentImages.length < 2) return;
    const currentIndex = currentImages.findIndex((item) => item.id === lightboxMediaIdRef.current);
    const nextIndex = (currentIndex + direction + currentImages.length) % currentImages.length;
    setLightboxMediaId(currentImages[nextIndex].id);
  }

  function retryScan() {
    operationGenerationRef.current += 1;
    locationAttemptRef.current += 1;
    startRequestRef.current = null;
    scanIdRef.current = null;
    submittingRef.current = false;
    setLocationRequesting(false);
    setLocationPermission("unknown");
    setScan(null);
    setProduct(null);
    setMedia([]);
    setForms([]);
    setFormAnswers({});
    setFormErrors({});
    setSubmittedForms(new Set());
    setMediaError("");
    setFailedMediaIds(new Set());
    setStartAttempt((attempt) => attempt + 1);
    setView("loading");
    setMessage("Verifying QR code...");
  }

  function continueWithoutLocation() {
    locationAttemptRef.current += 1;
    setLocationRequesting(false);
    const scanId = scanIdRef.current;
    if (scanId) {
      void submitLocation(scanId, { location_status: "SKIPPED" });
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f6f7] text-[#202a32]">
      <header className="border-b border-[#dce1e5] bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5">
          <div>
            <p className="text-lg font-bold tracking-tight">PRODUCT INFORMATION</p>
            <p className="text-xs tracking-[0.2em] text-slate-500">
              DIGITAL PRODUCT CATALOGUE
            </p>
          </div>
          <span
            role="status"
            aria-live="polite"
            className="text-xs font-semibold uppercase tracking-widest text-slate-500"
          >
            {accessStatusLabel[view]}
          </span>
        </div>
      </header>

      {view !== "product" ? (
        <section className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-6 text-center">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#e8edf1] text-2xl">
            {view === "error" ? "!" : view === "blocked" ? "×" : "◇"}
          </div>

          <h1 className="text-2xl font-bold tracking-tight">
            {view === "loading"
              ? "Verifying product"
              : view === "location"
                ? "Location verification"
                : view === "blocked"
                  ? "Access restricted"
                  : view === "error"
                    ? "Unable to open product"
                    : "Please wait"}
          </h1>

          <p role="status" aria-live="polite" className="mt-3 max-w-md text-sm leading-7 text-slate-600">
            {message}
          </p>

          {view === "location" && scan?.location_requested && (
            <div className="mt-8">
              {locationPermission === "denied" && (
                <p className="mb-4 max-w-md text-sm leading-6 text-slate-600">
                  Location is blocked in this browser. Change this site&apos;s Location setting to Allow, then return here and continue.
                </p>
              )}
              <div className="flex flex-wrap justify-center gap-3">
                <button
                  onClick={requestLocation}
                  disabled={busy || locationRequesting}
                  className="rounded-lg bg-[#263c4b] px-6 py-3 text-sm font-semibold text-white hover:bg-[#344f61] disabled:opacity-50"
                >
                  {locationRequesting
                    ? "Waiting for location…"
                    : locationPermission === "denied"
                      ? "Continue after allowing location"
                      : "Share location"}
                </button>

                {scan.location_requirement === "SKIPPABLE" && (
                  <button
                    onClick={() => {
                      continueWithoutLocation();
                    }}
                    disabled={busy}
                    className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50"
                  >
                    Continue without location
                  </button>
                )}
              </div>
            </div>
          )}

          {view === "location" && !scan?.location_requested && (
            <button
                onClick={continueWithoutLocation}
              className="mt-8 rounded-lg bg-[#263c4b] px-6 py-3 text-sm font-semibold text-white"
            >
              Continue
            </button>
          )}

          {view === "error" && (
            <button
              onClick={retryScan}
              className="mt-8 rounded-lg bg-[#263c4b] px-6 py-3 text-sm font-semibold text-white"
            >
              Try again
            </button>
          )}

          {view === "blocked" && scan?.location_requested && (
            <div className="mt-8">
              {locationPermission === "denied" && (
                <p className="mb-4 max-w-md text-sm leading-6 text-slate-600">
                  Reloading does not change a saved Location denial. Update this site&apos;s browser permission first, then start a new check.
                </p>
              )}
              <button
                onClick={retryScan}
                className="rounded-lg bg-[#263c4b] px-6 py-3 text-sm font-semibold text-white"
              >
                {locationPermission === "denied" ? "Start again after allowing location" : "Try again"}
              </button>
            </div>
          )}
        </section>
      ) : (
        <>
          <section className="bg-[#233746] text-white">
            <div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 md:grid-cols-2 md:items-center md:py-24">
              <div>
                <p className="text-xs font-semibold tracking-[0.25em] text-slate-300">
                  PRODUCT / {product?.sku}
                </p>
                <h1 className="mt-5 text-4xl font-bold tracking-tight md:text-6xl">
                  {title}
                </h1>
                {(shortDescription || description) && (
                  <p className="mt-6 max-w-xl text-base leading-8 text-slate-300">
                    {shortDescription || description}
                  </p>
                )}
                <p className="mt-8 text-xs tracking-widest text-slate-400">
                  VERIFIED PRODUCT INFORMATION
                </p>
              </div>

              {images[0] && !failedMediaIds.has(images[0].id) && (
                <button
                  type="button"
                  onClick={(event) => openLightbox(images[0].id, event.currentTarget)}
                  aria-label={`View image of ${images[0].alt_text || title}`}
                  className="relative block h-72 overflow-hidden rounded-xl bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white md:h-96"
                >
                  <Image
                    src={`/api/v1/public/scans/${scan?.scan_id}/media/${images[0].id}/file`}
                    alt={images[0].alt_text || title}
                    fill
                    unoptimized
                    sizes="(max-width: 768px) 100vw, 50vw"
                    className="object-contain"
                    priority
                    onError={() => markMediaFailed(images[0].id)}
                  />
                </button>
              )}
              {images[0] && failedMediaIds.has(images[0].id) && (
                <div className="flex h-72 items-center justify-center rounded-xl bg-white/10 text-sm text-slate-300 md:h-96">
                  Product image unavailable
                </div>
              )}
            </div>
          </section>

          <div className="mx-auto max-w-7xl space-y-16 px-5 py-16">
            {(mediaLoading || mediaError) && (
              <section aria-live="polite" className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
                {mediaLoading ? "Loading product media…" : mediaError}
                {mediaError && scan?.scan_id && (
                  <button
                    disabled={mediaLoading}
                    className="ml-3 font-semibold text-[#263c4b] underline"
                    onClick={async () => {
                      setMediaLoading(true);
                      setMediaError("");
                      setFailedMediaIds(new Set());
                      try {
                        const response = await fetch(`/api/v1/public/scans/${encodeURIComponent(scan.scan_id)}/media`);
                        const result = await readResponse(response, "Product media could not be loaded.", isMediaList);
                        if (mountedRef.current) setMedia(result);
                      } catch (error) {
                        if (mountedRef.current) {
                          setMediaError(error instanceof Error ? error.message : "Product media could not be loaded.");
                        }
                      } finally {
                        if (mountedRef.current) setMediaLoading(false);
                      }
                    }}
                  >Retry media</button>
                )}
              </section>
            )}

            {unsupportedMedia.length > 0 && (
              <p role="status" className="text-sm text-slate-500">
                Some product files use a format this page cannot display.
              </p>
            )}
            {!mediaLoading && !mediaError && media.length === 0 && (
              <p role="status" className="text-sm text-slate-500">
                No product media is available for this version.
              </p>
            )}
            <section>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-bold tracking-[0.2em] text-slate-500">
                    PRODUCT OVERVIEW
                  </p>
                  <h2 className="mt-2 text-3xl font-bold">Overview</h2>
                </div>
                <p className="text-sm text-slate-500">
                  SKU: {product?.sku}
                </p>
              </div>
              {description && (
                <p className="mt-6 max-w-4xl leading-8 text-slate-600">
                  {description}
                </p>
              )}
              {!hasProductDetails && (
                <p className="mt-6 max-w-4xl leading-7 text-slate-500">
                  Additional product details are not available for this version.
                </p>
              )}
              {officialLinks && (
                <a
                  href={officialLinks.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-5 inline-flex text-sm font-semibold text-[#263c4b] underline underline-offset-4"
                >
                  View product information from {officialLinks.contactName} ↗
                </a>
              )}
            </section>

            {forms.map((form) => (
              <section key={form.id} className="rounded-2xl border border-slate-200 bg-white p-6 md:p-8">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold tracking-[0.2em] text-slate-500">PRODUCT ENQUIRY</p>
                    <h2 className="mt-2 text-2xl font-bold">{form.name}</h2>
                    {form.description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{form.description}</p>}
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-600">{form.requirement === "MANDATORY" ? "Required" : "Optional"}</span>
                </div>
                {submittedForms.has(form.id) ? (
                  <p role="status" className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">Thanks. Your response has been sent.</p>
                ) : (
                  <form onSubmit={(event) => void handleFormSubmit(event, form)} className="mt-5 space-y-4">
                    {form.schema.fields.map((field) => {
                      const value = formAnswers[form.id]?.[field.key];
                      const setValue = (nextValue: string | boolean) => setFormAnswers((current) => ({
                        ...current,
                        [form.id]: { ...current[form.id], [field.key]: nextValue },
                      }));
                      if (field.type === "CHECKBOX") {
                        return <label key={field.key} className="flex items-start gap-3 text-sm text-slate-700">
                          <input type="checkbox" required={field.required} checked={value === true} onChange={(event) => setValue(event.target.checked)} className="mt-1 accent-[#263c4b]" />
                          <span>{field.label}{field.required && <span className="text-rose-600"> *</span>}</span>
                        </label>;
                      }
                      return <label key={field.key} className="block text-sm font-medium text-slate-700">
                        {field.label}{field.required && <span className="text-rose-600"> *</span>}
                        {field.type === "TEXTAREA" ? (
                          <textarea required={field.required} maxLength={field.max_length ?? 500} value={typeof value === "string" ? value : ""} onChange={(event) => setValue(event.target.value)} rows={4} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#263c4b]" />
                        ) : field.type === "SELECT" ? (
                          <select required={field.required} value={typeof value === "string" ? value : ""} onChange={(event) => setValue(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-[#263c4b]"><option value="">Choose an option</option>{(field.options ?? []).map((option) => <option key={option} value={option}>{option}</option>)}</select>
                        ) : (
                          <input required={field.required} type={field.type === "EMAIL" ? "email" : field.type === "PHONE" ? "tel" : "text"} inputMode={field.type === "PHONE" ? "tel" : undefined} autoComplete={field.type === "PHONE" ? "tel" : field.type === "EMAIL" ? "email" : undefined} pattern={field.type === "PHONE" ? "[+0-9() .-]{7,24}" : undefined} title={field.type === "PHONE" ? "Enter a phone number with 7 to 15 digits." : undefined} maxLength={field.max_length ?? 500} value={typeof value === "string" ? value : ""} onChange={(event) => setValue(event.target.value)} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#263c4b]" />
                        )}
                      </label>;
                    })}
                    <p className="text-xs leading-5 text-slate-500">Your response is stored with this product scan and visible to platform administrators.</p>
                    {formErrors[form.id] && <p role="alert" className="text-sm text-rose-700">{formErrors[form.id]}</p>}
                    {formErrors._page && <p role="status" className="text-sm text-rose-700">{formErrors._page}</p>}
                    <button disabled={submittingFormId === form.id} className="rounded-lg bg-[#263c4b] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">{submittingFormId === form.id ? "Sending…" : "Send enquiry"}</button>
                  </form>
                )}
              </section>
            ))}

            {galleryImages.length > 0 && (
              <section>
                <h2 className="text-2xl font-bold">Product gallery</h2>
                <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {galleryImages.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={(event) => openLightbox(item.id, event.currentTarget)}
                      aria-label={`View image of ${item.alt_text || item.original_filename}`}
                      className="relative block h-64 w-full overflow-hidden rounded-xl border border-slate-200 bg-white p-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#263c4b]"
                    >
                      {failedMediaIds.has(item.id) ? (
                        <div className="flex h-full items-center justify-center text-sm text-slate-500">Image unavailable</div>
                      ) : (
                        <Image
                          src={`/api/v1/public/scans/${scan?.scan_id}/media/${item.id}/file`}
                          alt={item.alt_text || item.original_filename}
                          fill
                          unoptimized
                          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                          className="object-contain p-3"
                          onError={() => markMediaFailed(item.id)}
                        />
                      )}
                    </button>
                  ))}
                </div>
              </section>
            )}

            {videos.length > 0 && (
              <section>
                <h2 className="text-2xl font-bold">Videos</h2>
                <div className="mt-6 grid gap-5 md:grid-cols-2">
                  {videos.map((item) => (
                    failedMediaIds.has(item.id) ? (
                      <div key={item.id} role="status" className="flex min-h-48 items-center justify-center rounded-xl bg-slate-200 p-6 text-center text-sm text-slate-600">
                        Video unavailable: {item.original_filename}
                      </div>
                    ) : (
                      <video
                        key={item.id}
                        controls
                        className="w-full rounded-xl bg-black"
                        src={`/api/v1/public/scans/${scan?.scan_id}/media/${item.id}/file`}
                        onError={() => markMediaFailed(item.id)}
                      />
                    )
                  ))}
                </div>
              </section>
            )}

            <ProductDetails
              features={features}
              benefits={benefits}
              applications={applications}
              materials={materials}
              specifications={specifications}
              customFields={customFields}
            />

            {documents.length > 0 && (
              <section>
                <h2 className="text-2xl font-bold">Documents</h2>
                <div className="mt-6 space-y-3">
                  {documents.map((item) => (
                    <a
                      key={item.id}
                      href={`/api/v1/public/scans/${scan?.scan_id}/media/${item.id}/file`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 text-sm hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <span className="break-all font-semibold text-slate-800">{item.original_filename}</span>
                      <span className="flex shrink-0 items-center gap-3 text-xs font-medium text-slate-500">
                        <span className="rounded bg-slate-100 px-2 py-1">{formatFileType(item)}</span>
                        <span>{formatFileSize(item.file_size_bytes)}</span>
                        <span aria-hidden="true">Open ↗</span>
                      </span>
                    </a>
                  ))}
                </div>
              </section>
            )}

            <section className="rounded-2xl bg-[#233746] p-8 text-white md:p-12">
              <p className="text-xs font-bold tracking-[0.2em] text-slate-300">
                EXTERNAL CONTACT
              </p>
              <h2 className="mt-3 text-3xl font-bold">Contact the product team</h2>
              <p className="mt-4 max-w-2xl leading-7 text-slate-300">
                Open the manufacturer&apos;s contact page for product questions,
                specifications or sales assistance.
              </p>
              {officialLinks ? (
                <a
                  href={officialLinks.contactUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-7 inline-flex rounded-lg bg-white px-6 py-3 text-sm font-semibold text-[#233746] hover:bg-slate-100"
                >
                  Contact {officialLinks.contactName} ↗
                </a>
              ) : (
                <p className="mt-7 text-sm text-slate-300">
                  Contact details are not available for this product.
                </p>
              )}
            </section>

            <footer className="flex flex-col gap-2 border-t border-slate-200 pt-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
              <span>Digital Product Catalogue</span>
              <span>
                Product version {product?.version_number} · {product?.sku}
              </span>
            </footer>
          </div>
        </>
      )}

      {lightboxImage && (
        <div
          ref={lightboxRef}
          role="dialog"
          aria-modal="true"
          aria-label="Product image viewer"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 p-4 text-white"
          onClick={(event) => { if (event.target === event.currentTarget) setLightboxMediaId(null); }}
        >
          <button
            ref={lightboxCloseRef}
            type="button"
            onClick={() => setLightboxMediaId(null)}
            aria-label="Close image viewer"
            data-lightbox-close
            className="absolute right-4 top-4 z-10 rounded-lg bg-white/10 px-4 py-3 text-sm font-semibold hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
          >Close <span aria-hidden="true">×</span></button>
          {lightboxImages.length > 1 && <>
            <button type="button" onClick={() => moveLightbox(-1)} aria-label="Previous image" className="absolute left-3 z-10 rounded-full bg-white/10 px-4 py-3 text-2xl hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">‹</button>
            <button type="button" onClick={() => moveLightbox(1)} aria-label="Next image" className="absolute right-3 z-10 rounded-full bg-white/10 px-4 py-3 text-2xl hover:bg-white/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">›</button>
          </>}
          <figure
            className="relative flex h-[80vh] w-full max-w-6xl touch-pan-y flex-col items-center justify-center pb-8"
            onTouchStart={(event) => { lightboxTouchStartXRef.current = event.touches.length === 1 ? event.touches[0].clientX : null; }}
            onTouchEnd={(event) => {
              const startX = lightboxTouchStartXRef.current;
              lightboxTouchStartXRef.current = null;
              if (startX === null || lightboxImagesRef.current.length < 2) return;
              const deltaX = event.changedTouches[0].clientX - startX;
              if (Math.abs(deltaX) >= 48) moveLightbox(deltaX < 0 ? 1 : -1);
            }}
          >
            <div className="relative min-h-0 w-full flex-1">
              <Image
                src={`/api/v1/public/scans/${scan?.scan_id}/media/${lightboxImage.id}/file`}
                alt={lightboxImage.alt_text || lightboxImage.original_filename}
                fill
                unoptimized
                sizes="100vw"
                className="object-contain"
                onError={() => { markMediaFailed(lightboxImage.id); setLightboxMediaId(null); }}
              />
            </div>
            <figcaption className="mt-3 text-center text-sm text-white/80">
              {lightboxImage.alt_text || lightboxImage.original_filename}
              {lightboxImages.length > 1 && <span className="ml-2 text-white/60">{lightboxImages.findIndex((item) => item.id === lightboxImage.id) + 1} of {lightboxImages.length}</span>}
            </figcaption>
          </figure>
        </div>
      )}
    </main>
  );
}

