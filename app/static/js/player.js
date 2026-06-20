(function () {
  function setupPlayer(config) {
    const video = document.getElementById(`video-${config.id}`);
    const error = document.getElementById(`video-error-${config.id}`);
    if (!video) return;
    fetch(config.apiUrl)
      .then((response) => {
        if (!response.ok) throw new Error("Нет доступа к playback URL");
        return response.json();
      })
      .then((payload) => {
        const url = payload.playback_url;
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = url;
          video.play().catch(() => {});
        } else if (window.Hls && Hls.isSupported()) {
          const hls = new Hls({ lowLatencyMode: true });
          hls.loadSource(url);
          hls.attachMedia(video);
          hls.on(Hls.Events.ERROR, function (_, data) {
            if (data.fatal && error) error.classList.remove("d-none");
          });
        } else if (error) {
          error.classList.remove("d-none");
        }
      })
      .catch(() => {
        if (error) error.classList.remove("d-none");
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    (window.bowlingPlayers || []).forEach(setupPlayer);
  });
})();
