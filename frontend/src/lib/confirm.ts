// A promise-based replacement for the browser's blocking window.confirm /
// window.alert. Follows the same module-level-store pattern as notifications.ts
// (no React context to thread), with a single <ConfirmHost/> mounted in the
// root layout that renders the actual themed dialog.

export type ConfirmVariant = "default" | "danger";

export type ConfirmOptions = {
  title: string;
  message?: string;
  /** Confirm button label. Defaults to a localized "OK" in the host. */
  confirmLabel?: string;
  /** Cancel button label. Defaults to a localized "Cancel" in the host. */
  cancelLabel?: string;
  /** "danger" styles the confirm button as destructive (used for deletes). */
  variant?: ConfirmVariant;
  /** Hide the cancel button — turns the dialog into an alert()-style notice. */
  noticeOnly?: boolean;
};

export type ConfirmRequest = ConfirmOptions & {
  id: number;
  resolve: (confirmed: boolean) => void;
};

type Listener = (req: ConfirmRequest | null) => void;

let listener: Listener | null = null;
let seq = 0;

/** The host registers itself here. Only one host is expected (root layout). */
export function _registerConfirmHost(fn: Listener | null) {
  listener = fn;
}

/**
 * Show a themed confirm dialog. Resolves true if confirmed, false if cancelled
 * or dismissed. If no host is mounted (e.g. SSR), falls back to window.confirm
 * so callers never hang.
 */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  if (!listener || typeof window === "undefined") {
    if (typeof window !== "undefined" && !options.noticeOnly) {
      return Promise.resolve(window.confirm(options.message || options.title));
    }
    return Promise.resolve(true);
  }
  return new Promise<boolean>((resolve) => {
    listener?.({ ...options, id: ++seq, resolve });
  });
}

/**
 * alert()-style single-button notice built on the same dialog. Resolves once
 * dismissed. Use for error/info messages that used to call window.alert.
 */
export function noticeDialog(options: Omit<ConfirmOptions, "noticeOnly" | "variant">): Promise<void> {
  return confirmDialog({ ...options, noticeOnly: true }).then(() => undefined);
}
