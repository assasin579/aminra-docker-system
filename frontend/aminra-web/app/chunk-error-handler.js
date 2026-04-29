// Chunk Loading Error Handler
// This prevents ChunkLoadError from breaking the application

if (typeof window !== "undefined") {
  window.addEventListener("unhandledrejection", (event) => {
    if (event.reason && event.reason.name === "ChunkLoadError") {
      console.log("ChunkLoadError detected, reloading page...");
      // Prevent the error from being logged to console
      event.preventDefault();

      // Add small delay to prevent immediate reload loop
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    }
  });

  // Handle dynamic import chunk loading errors
  const originalImport = window.__webpack_require__;
  if (originalImport) {
    window.__webpack_require__ = function (chunkId) {
      try {
        return originalImport(chunkId);
      } catch (error) {
        if (error.name === "ChunkLoadError") {
          console.log("Chunk loading failed, attempting reload...");
          setTimeout(() => {
            window.location.reload();
          }, 1000);
          return Promise.reject(error);
        }
        throw error;
      }
    };
  }
}
