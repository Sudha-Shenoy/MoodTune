/**
 * MoodTune - Music Player & Discovery Controller
 * Module 07: YouTube IFrame Player API Integration & Up Next Queue
 */

(function () {
    "use strict";

    function escapeHTML(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    const MoodTunePlayer = {
        player: null,
        isAPIReady: false,
        isPlayerReady: false,
        pendingVideo: null,
        queue: [],
        currentIndex: -1,
        isPlaying: false,
        isMuted: false,
        volume: 80,
        updateTimer: null,
        consecutiveErrors: 0,
        isUserSeeking: false,
        isMinimized: false,
        isQueueOpen: false,
        lastMeasuredHeight: 0,
        failedVideoIds: new Set(),
        skipTimer: null,

        // Cached DOM Elements
        elements: {},

        measureAndReserveAnchorHeight: function () {
            if (!this.elements.nowPlayingSection || !this.elements.playerAnchor) return;
            const isDocked = this.elements.nowPlayingSection.classList.contains("docked");
            const isMin = this.elements.nowPlayingSection.classList.contains("minimized");
            const isHidden = (this.elements.nowPlayingSection.style.display === "none");

            if (!isDocked && !isMin && !isHidden) {
                const height = this.elements.nowPlayingSection.offsetHeight;
                if (height > 0) {
                    this.lastMeasuredHeight = height;
                    this.elements.playerAnchor.style.minHeight = height + "px";
                }
            }
        },

        init: function () {
            this.cacheElements();
            this.bindEvents();
            this.initSSRQueue();
            this.setupScrollDocking();
            this.loadYouTubeIframeAPI();
        },

        cacheElements: function () {
            this.elements = {
                playerAnchor: document.getElementById("moodtunePlayerAnchor"),
                nowPlayingSection: document.getElementById("moodtuneNowPlaying"),
                nowPlayingQuote: document.getElementById("nowPlayingQuote"),
                nowPlayingMoodBadge: document.getElementById("nowPlayingMoodBadge"),
                ytWrapper: document.getElementById("ytPlayerWrapper"),
                statusBadge: document.getElementById("nowPlayingStatusBadge"),
                statusText: document.getElementById("nowPlayingStatusText"),
                soundwaveAnim: document.getElementById("nowPlayingSoundwave"),
                title: document.getElementById("nowPlayingTitle"),
                channel: document.getElementById("nowPlayingChannel"),
                prevBtn: document.getElementById("playerPrevBtn"),
                playPauseBtn: document.getElementById("playerPlayPauseBtn"),
                playIcon: document.querySelector(".player-play-icon"),
                pauseIcon: document.querySelector(".player-pause-icon"),
                nextBtn: document.getElementById("playerNextBtn"),
                currentTime: document.getElementById("playerCurrentTime"),
                progressBar: document.getElementById("playerProgressBar"),
                duration: document.getElementById("playerDuration"),
                muteBtn: document.getElementById("playerMuteBtn"),
                volIconHigh: document.querySelector(".vol-icon-high"),
                volIconMute: document.querySelector(".vol-icon-mute"),
                volumeSlider: document.getElementById("playerVolumeSlider"),
                queueToggleBtn: document.getElementById("playerQueueToggleBtn"),
                queueDrawer: document.getElementById("playerQueueDrawer"),
                queueList: document.getElementById("playerQueueList"),
                queueCountBadge: document.getElementById("queueCountBadge"),
                queueCloseBtn: document.getElementById("queueCloseBtn"),
                minimizeBtn: document.getElementById("playerMinimizeBtn"),
                expandBtn: document.getElementById("playerExpandBtn"),
                closeBtn: document.getElementById("playerCloseBtn"),
                resultsGrid: document.getElementById("youtubeResultsGrid")
            };
        },

        bindEvents: function () {
            const self = this;

            // Play / Pause Toggle
            if (this.elements.playPauseBtn) {
                this.elements.playPauseBtn.addEventListener("click", () => self.togglePlayPause());
            }

            // Previous / Next Buttons
            if (this.elements.prevBtn) {
                this.elements.prevBtn.addEventListener("click", () => self.playPrevious());
            }
            if (this.elements.nextBtn) {
                this.elements.nextBtn.addEventListener("click", () => self.playNext());
            }

            // Scrubber / Progress Bar
            if (this.elements.progressBar) {
                this.elements.progressBar.addEventListener("input", (e) => {
                    self.isUserSeeking = true;
                    if (self.isPlayerReady && self.player && typeof self.player.getDuration === "function") {
                        const dur = self.player.getDuration() || 0;
                        const targetTime = (parseFloat(e.target.value) / 100) * dur;
                        if (self.elements.currentTime) {
                            self.elements.currentTime.textContent = self.formatTime(targetTime);
                        }
                    }
                });

                this.elements.progressBar.addEventListener("change", (e) => {
                    self.seekTo(parseFloat(e.target.value));
                    self.isUserSeeking = false;
                });
            }

            // Volume Controls
            if (this.elements.volumeSlider) {
                this.elements.volumeSlider.addEventListener("input", (e) => {
                    self.setVolume(parseFloat(e.target.value));
                });
            }

            if (this.elements.muteBtn) {
                this.elements.muteBtn.addEventListener("click", () => self.toggleMute());
            }

            // Queue Drawer Toggle & Close
            if (this.elements.queueToggleBtn) {
                this.elements.queueToggleBtn.addEventListener("click", () => self.toggleQueue());
            }

            if (this.elements.queueCloseBtn) {
                this.elements.queueCloseBtn.addEventListener("click", () => self.toggleQueue(false));
            }

            // Minimize / Expand / Close Actions
            if (this.elements.minimizeBtn) {
                this.elements.minimizeBtn.addEventListener("click", () => self.minimizePlayer());
            }

            if (this.elements.expandBtn) {
                this.elements.expandBtn.addEventListener("click", () => self.expandPlayer());
            }

            if (this.elements.closeBtn) {
                this.elements.closeBtn.addEventListener("click", () => self.closePlayer());
            }

            // Clicking track title in minimized or docked mode expands player
            if (this.elements.title) {
                this.elements.title.addEventListener("click", () => {
                    if (self.isMinimized || (self.elements.nowPlayingSection && self.elements.nowPlayingSection.classList.contains("docked"))) {
                        self.expandPlayer();
                    }
                });
            }

            // Event Delegation for Music Cards: Play Button & Play Overlay
            if (this.elements.resultsGrid) {
                this.elements.resultsGrid.addEventListener("click", (e) => {
                    const playBtn = e.target.closest(".btn-play-song");
                    const overlay = e.target.closest(".music-card-play-overlay");
                    const card = e.target.closest(".music-card");

                    if ((playBtn || overlay) && card) {
                        e.preventDefault();
                        const videoId = card.dataset.videoId;
                        if (videoId) {
                            self.playByVideoId(videoId);
                        }
                    }
                });
            }
        },

        // Load YouTube IFrame API (single-instance loader)
        loadYouTubeIframeAPI: function () {
            if (window.YT && window.YT.Player) {
                this.onAPIReady();
                return;
            }

            const self = this;
            const existingCallback = window.onYouTubeIframeAPIReady;
            window.onYouTubeIframeAPIReady = function () {
                if (typeof existingCallback === "function") existingCallback();
                self.onAPIReady();
            };

            if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
                const tag = document.createElement("script");
                tag.src = "https://www.youtube.com/iframe_api";
                const firstScript = document.getElementsByTagName("script")[0];
                if (firstScript && firstScript.parentNode) {
                    firstScript.parentNode.insertBefore(tag, firstScript);
                } else {
                    document.head.appendChild(tag);
                }
            }
        },

        onAPIReady: function () {
            this.isAPIReady = true;

            // If user clicked "Play Song" before the IFrame API completed loading
            if (this.pendingVideo) {
                const pending = this.pendingVideo;
                this.pendingVideo = null;
                this.ensurePlayer(pending.videoId, pending.index);
            }
        },

        ensurePlayer: function (videoIdToPlay, indexToSet) {
            if (this.player || !this.isAPIReady) return;
            const hostElem = document.getElementById("ytPlayerHost");
            if (!hostElem) return;

            // Ensure player container is visible before initializing YT.Player so dimensions > 200px
            if (this.elements.nowPlayingSection && this.elements.nowPlayingSection.style.display === "none") {
                this.showNowPlayingUI();
            }

            const self = this;
            const safeOrigin = (window.location.origin && window.location.origin !== "null")
                ? window.location.origin
                : undefined;

            try {
                this.player = new window.YT.Player("ytPlayerHost", {
                    host: "https://www.youtube.com",
                    height: "100%",
                    width: "100%",
                    videoId: videoIdToPlay || undefined,
                    playerVars: {
                        autoplay: videoIdToPlay ? 1 : 0,
                        controls: 0,
                        disablekb: 0,
                        enablejsapi: 1,
                        fs: 0,
                        modestbranding: 1,
                        origin: safeOrigin,
                        widget_referrer: window.location.href,
                        rel: 0,
                        playsinline: 1
                    },
                    events: {
                        onReady: function (event) {
                            self.onPlayerReady(event);
                        },
                        onStateChange: function (event) {
                            self.onPlayerStateChange(event);
                        },
                        onError: function (event) {
                            self.onPlayerError(event);
                        }
                    }
                });
            } catch (err) {
                console.error("Error creating YouTube player instance:", err);
            }
        },

        onPlayerReady: function (event) {
            this.isPlayerReady = true;

            if (this.player && typeof this.player.setVolume === "function") {
                this.player.setVolume(this.volume);
            }

            // If user clicked another track while player was initializing
            if (this.pendingVideo) {
                const pending = this.pendingVideo;
                this.pendingVideo = null;
                this.playSong(pending.videoId, pending.index);
            } else if (this.currentIndex >= 0 && this.currentIndex < this.queue.length) {
                const curTrack = this.queue[this.currentIndex];
                if (curTrack && curTrack.video_id && !this.failedVideoIds.has(curTrack.video_id)) {
                    try {
                        if (typeof this.player.playVideo === "function") {
                            this.player.playVideo();
                        }
                    } catch (e) {}
                }
            }
        },

        onPlayerStateChange: function (event) {
            const state = event.data;

            // Handle YT.PlayerState
            if (state === window.YT.PlayerState.PLAYING) {
                this.isPlaying = true;
                this.consecutiveErrors = 0;
                this.updatePlayPauseUI(true);
                this.showStatusMessage("NOW PLAYING", false);
                this.startProgressTimer();
                this.syncActiveTrack();
            } else if (state === window.YT.PlayerState.PAUSED) {
                this.isPlaying = false;
                this.updatePlayPauseUI(false);
                this.showStatusMessage("PAUSED", false);
                this.stopProgressTimer();
            } else if (state === window.YT.PlayerState.ENDED) {
                this.isPlaying = false;
                this.updatePlayPauseUI(false);
                this.stopProgressTimer();
                this.onTrackEnded();
            } else if (state === window.YT.PlayerState.BUFFERING) {
                this.showStatusMessage("Buffering...", false);
            } else if (state === window.YT.PlayerState.CUED) {
                // Autoplay blocked handling
                this.isPlaying = false;
                this.updatePlayPauseUI(false);
                this.showStatusMessage("▶ Press Play to start", false);
            }
        },

        onPlayerError: function (event) {
            const errorCode = event.data;
            const currentVideoId = (this.currentIndex >= 0 && this.currentIndex < this.queue.length)
                ? this.queue[this.currentIndex].video_id
                : (this.pendingVideo ? this.pendingVideo.videoId : "unknown");

            // Required exact diagnostic log format (never logging API keys or credentials)
            console.warn(`YouTube Player Error:\nvideo_id=${currentVideoId}\nerror_code=${errorCode}`);

            if (currentVideoId && currentVideoId !== "unknown") {
                this.failedVideoIds.add(currentVideoId);
                this.markVideoUnavailable(currentVideoId);
            }

            this.stopProgressTimer();
            this.isPlaying = false;
            this.updatePlayPauseUI(false);

            if (this.skipTimer) {
                clearTimeout(this.skipTimer);
                this.skipTimer = null;
            }

            // Error 153: Missing or unapproved referrer/client identification
            if (errorCode === 153) {
                console.error("YouTube Player Error 153: Player identity/referrer validation failure. Halting automatic skip loop.");
                this.showStatusMessage("Playback identity error (153). Please refresh or check browser settings.", true);
                return;
            }

            // Error 101/150: Owner disabled embedded playback
            if (errorCode === 101 || errorCode === 150) {
                this.showStatusMessage("That video can't be played here. Trying the next song...", true);
            } else if (errorCode === 100) {
                // Error 100: Video removed or private
                this.showStatusMessage("This video is unavailable. Trying the next song...", true);
            } else {
                // Other errors (e.g. 2, 5)
                this.showStatusMessage("This song can't be played. Trying the next song...", true);
            }

            // Skip to next playable song without repeating failed video
            const self = this;
            this.skipTimer = setTimeout(() => {
                self.skipTimer = null;
                self.playNextPlayableSong();
            }, 1200);
        },

        markVideoUnavailable: function (videoId) {
            if (!videoId) return;

            // Mark card in discovery song list
            const cards = document.querySelectorAll(`.music-card[data-video-id="${videoId}"]`);
            cards.forEach((card) => {
                card.classList.add("playback-unavailable");
                const playBtn = card.querySelector(".btn-play-song");
                if (playBtn) {
                    playBtn.setAttribute("title", "Unavailable in embedded player - click Watch to open on YouTube");
                    playBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                            <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"></line>
                            <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"></line>
                        </svg>
                        <span>Unavailable</span>
                    `;
                }
            });

            // Mark item in queue drawer
            if (this.elements.queueList) {
                const qItems = this.elements.queueList.querySelectorAll(`.queue-track-item[data-video-id="${videoId}"]`);
                qItems.forEach((item) => {
                    item.classList.add("queue-item-unavailable");
                    const actionEl = item.querySelector(".queue-item-action");
                    if (actionEl) {
                        actionEl.innerHTML = `<span class="queue-item-blocked" title="Unavailable in embedded player" style="color:#ff6b6b;font-size:0.75rem;">✕</span>`;
                    }
                });
            }
            this.updateNavButtons();
        },

        playNextPlayableSong: function () {
            if (!this.queue || this.queue.length === 0) {
                this.showStatusMessage("No songs in queue.", true);
                return;
            }

            let nextIdx = -1;
            // 1. Search ahead from current track
            for (let i = this.currentIndex + 1; i < this.queue.length; i++) {
                if (!this.failedVideoIds.has(this.queue[i].video_id)) {
                    nextIdx = i;
                    break;
                }
            }

            // 2. If no unfailed track ahead, search from beginning of queue
            if (nextIdx === -1) {
                for (let i = 0; i <= this.currentIndex && i < this.queue.length; i++) {
                    if (!this.failedVideoIds.has(this.queue[i].video_id)) {
                        nextIdx = i;
                        break;
                    }
                }
            }

            if (nextIdx !== -1) {
                const nextTrack = this.queue[nextIdx];
                this.playSong(nextTrack.video_id, nextIdx);
            } else {
                // All songs in queue have failed
                this.isPlaying = false;
                this.updatePlayPauseUI(false);
                this.stopProgressTimer();
                this.clearActiveHighlights();
                this.showStatusMessage("No playable songs are available in this mix. Try generating a new mix.", true);
            }
        },

        onTrackEnded: function () {
            if (this.currentIndex + 1 < this.queue.length) {
                this.playNext();
            } else {
                // End of queue: stop cleanly without infinite loops
                this.showStatusMessage("Queue completed", false);
                if (this.elements.progressBar) this.elements.progressBar.value = 0;
                if (this.elements.currentTime) this.elements.currentTime.textContent = "00:00";
                this.clearActiveHighlights();
                this.updateNavButtons();
            }
        },

        // Queue Management
        initSSRQueue: function () {
            if (!this.elements.resultsGrid) return;
            const cards = this.elements.resultsGrid.querySelectorAll(".music-card");
            if (!cards || cards.length === 0) return;

            const ssrQueue = [];
            cards.forEach((card) => {
                const videoId = card.dataset.videoId;
                const titleEl = card.querySelector(".music-card-title");
                const channelEl = card.querySelector(".music-card-channel span") || card.querySelector(".song-meta-channel span");
                const thumbEl = card.querySelector(".music-card-thumb");
                const watchEl = card.querySelector(".btn-youtube-watch");
                const quoteEl = card.querySelector(".song-row-quote");

                if (videoId) {
                    ssrQueue.push({
                        video_id: videoId,
                        title: titleEl ? titleEl.textContent.trim() : "Music Track",
                        channel_title: channelEl ? channelEl.textContent.trim() : "YouTube",
                        thumbnail: thumbEl ? thumbEl.src : "",
                        youtube_url: watchEl ? watchEl.href : `https://www.youtube.com/watch?v=${videoId}`,
                        moodQuote: quoteEl ? quoteEl.textContent.trim().replace(/^["“]|["”]$/g, "") : ""
                    });
                }
            });

            if (ssrQueue.length > 0) {
                this.setQueue(ssrQueue);
            }
        },

        setQueue: function (videos, moodQuotes) {
            if (!Array.isArray(videos)) return;
            if (this.skipTimer) {
                clearTimeout(this.skipTimer);
                this.skipTimer = null;
            }
            this.failedVideoIds.clear();
            const quotes = (Array.isArray(moodQuotes) && moodQuotes.length > 0) ? moodQuotes : [];
            this.queue = videos.map((track, idx) => {
                const assignedQuote = track.moodQuote || (quotes.length > 0 ? quotes[idx % quotes.length] : "");
                return Object.assign({}, track, { moodQuote: assignedQuote });
            });

            if (this.elements.queueCountBadge) {
                this.elements.queueCountBadge.textContent = String(this.queue.length);
            }
            const queueSub = document.getElementById("queueSubtitleText");
            if (queueSub) {
                queueSub.textContent = `${this.queue.length} songs in this mix`;
            }
            const heroCount = document.getElementById("mixHeroCountBadge");
            if (heroCount) {
                heroCount.textContent = `${this.queue.length} songs selected for your vibe`;
            }
            const collPill = document.getElementById("collectionCountPill");
            if (collPill) {
                collPill.textContent = `${this.queue.length} Songs`;
            }
            this.renderQueueUI();
            this.updateNavButtons();
        },

        getQueue: function () {
            return this.queue;
        },

        renderQueueUI: function () {
            if (!this.elements.queueList) return;

            const self = this;
            if (this.queue.length === 0) {
                this.elements.queueList.innerHTML = `<div class="queue-empty-msg">No tracks in queue.</div>`;
                return;
            }

            this.elements.queueList.innerHTML = this.queue.map((track, idx) => {
                const isActive = (idx === self.currentIndex);
                const isFailed = self.failedVideoIds.has(track.video_id);
                const quoteSnippet = track.moodQuote ? `<div class="queue-item-quote" title="${escapeHTML(track.moodQuote)}">“${escapeHTML(track.moodQuote)}”</div>` : "";
                return `
                    <div class="queue-track-item ${isActive ? "active-queue-item" : ""} ${isFailed ? "queue-item-unavailable" : ""}" data-index="${idx}" data-video-id="${escapeHTML(track.video_id)}">
                        <span class="queue-item-idx">${idx + 1}</span>
                        <div class="queue-item-art">
                            <span class="queue-item-icon">🎵</span>
                        </div>
                        <div class="queue-item-info">
                            <div class="queue-item-title" title="${escapeHTML(track.title)}">${escapeHTML(track.title)}</div>
                            <div class="queue-item-channel">${escapeHTML(track.channel_title)}</div>
                            ${quoteSnippet}
                        </div>
                        <div class="queue-item-action">
                            ${isFailed ? `
                                <span class="queue-item-blocked" title="Unavailable in embedded player" style="color:#ff6b6b;font-size:0.75rem;">✕</span>
                            ` : (isActive ? `
                                <div class="soundwave-bars" aria-hidden="true">
                                    <span class="soundwave-bar"></span>
                                    <span class="soundwave-bar"></span>
                                    <span class="soundwave-bar"></span>
                                </div>
                            ` : `
                                <span class="queue-play-glyph">▶</span>
                            `)}
                        </div>
                    </div>
                `;
            }).join("");

            // Attach click listeners to queue items
            this.elements.queueList.querySelectorAll(".queue-track-item").forEach((item) => {
                item.addEventListener("click", () => {
                    const idx = parseInt(item.dataset.index, 10);
                    const vid = item.dataset.videoId;
                    if (!isNaN(idx) && vid) {
                        self.playSong(vid, idx);
                    }
                });
            });
        },

        toggleQueue: function (forceOpen) {
            if (!this.elements.queueDrawer) return;

            if (typeof forceOpen === "boolean") {
                this.isQueueOpen = forceOpen;
            } else {
                this.isQueueOpen = !this.isQueueOpen;
            }

            this.elements.queueDrawer.style.display = this.isQueueOpen ? "block" : "none";
            if (this.elements.queueToggleBtn) {
                this.elements.queueToggleBtn.classList.toggle("active", this.isQueueOpen);
            }
        },

        playByVideoId: function (videoId) {
            let idx = this.queue.findIndex((v) => v.video_id === videoId);
            if (idx === -1) {
                const card = document.querySelector(`.music-card[data-video-id="${videoId}"]`);
                if (card) {
                    const titleEl = card.querySelector(".music-card-title");
                    const channelEl = card.querySelector(".music-card-channel span") || card.querySelector(".song-meta-channel span");
                    const thumbEl = card.querySelector(".music-card-thumb");
                    const watchEl = card.querySelector(".btn-youtube-watch");
                    const quoteEl = card.querySelector(".song-row-quote");
                    this.queue.push({
                        video_id: videoId,
                        title: titleEl ? titleEl.textContent.trim() : "Music Track",
                        channel_title: channelEl ? channelEl.textContent.trim() : "YouTube",
                        thumbnail: thumbEl ? thumbEl.src : "",
                        youtube_url: watchEl ? watchEl.href : `https://www.youtube.com/watch?v=${videoId}`,
                        moodQuote: quoteEl ? quoteEl.textContent.trim().replace(/^["“]|["”]$/g, "") : ""
                    });
                    idx = this.queue.length - 1;
                    this.renderQueueUI();
                }
            }
            this.playSong(videoId, idx);
        },

        playSong: function (videoId, index) {
            if (!videoId) return;

            if (this.failedVideoIds.has(videoId)) {
                this.showStatusMessage("That video can't be played here. Choose another song.", true);
                return;
            }

            if (this.skipTimer) {
                clearTimeout(this.skipTimer);
                this.skipTimer = null;
            }

            if (typeof index === "number" && index >= 0) {
                this.currentIndex = index;
            } else {
                this.currentIndex = this.queue.findIndex((v) => v.video_id === videoId);
            }

            const track = (this.currentIndex >= 0 && this.currentIndex < this.queue.length)
                ? this.queue[this.currentIndex]
                : { video_id: videoId, title: "Music Track", channel_title: "YouTube", thumbnail: "" };

            this.updateTrackMetadataUI(track);
            this.showNowPlayingUI();
            this.syncActiveTrack();
            this.updateNavButtons();

            if (!this.player) {
                if (this.isAPIReady) {
                    this.showStatusMessage("Loading...", false);
                    this.ensurePlayer(videoId, this.currentIndex);
                } else {
                    this.pendingVideo = { videoId, index: this.currentIndex };
                    this.showStatusMessage("Initializing player...", false);
                }
                return;
            }

            if (!this.isPlayerReady) {
                this.pendingVideo = { videoId, index: this.currentIndex };
                this.showStatusMessage("Loading...", false);
                return;
            }

            try {
                this.showStatusMessage("Loading...", false);
                this.player.loadVideoById(videoId);
            } catch (err) {
                console.error("Error invoking loadVideoById:", err);
                this.showStatusMessage("▶ Press Play to start", false);
            }
        },

        togglePlayPause: function () {
            if (!this.isPlayerReady || !this.player) return;

            try {
                const state = typeof this.player.getPlayerState === "function" ? this.player.getPlayerState() : -1;
                if (state === window.YT.PlayerState.PLAYING) {
                    this.player.pauseVideo();
                } else {
                    this.player.playVideo();
                }
            } catch (err) {
                console.warn("Could not toggle play/pause:", err);
            }
        },

        playNext: function () {
            if (!this.queue || this.queue.length === 0) return;
            let nextIdx = -1;
            for (let i = this.currentIndex + 1; i < this.queue.length; i++) {
                if (!this.failedVideoIds.has(this.queue[i].video_id)) {
                    nextIdx = i;
                    break;
                }
            }
            if (nextIdx !== -1) {
                this.playSong(this.queue[nextIdx].video_id, nextIdx);
            } else {
                this.showStatusMessage("End of playable queue.", false);
            }
        },

        playPrevious: function () {
            if (!this.queue || this.queue.length === 0) return;

            // If more than 3 seconds in, restart track
            try {
                const curTime = (this.isPlayerReady && this.player && typeof this.player.getCurrentTime === "function")
                    ? this.player.getCurrentTime()
                    : 0;
                if (curTime > 3) {
                    this.player.seekTo(0, true);
                    return;
                }
            } catch (e) {}

            let prevIdx = -1;
            for (let i = this.currentIndex - 1; i >= 0; i--) {
                if (!this.failedVideoIds.has(this.queue[i].video_id)) {
                    prevIdx = i;
                    break;
                }
            }

            if (prevIdx !== -1) {
                this.playSong(this.queue[prevIdx].video_id, prevIdx);
            } else if (this.isPlayerReady && this.player && typeof this.player.seekTo === "function") {
                this.player.seekTo(0, true);
            }
        },

        seekTo: function (percent) {
            if (!this.isPlayerReady || !this.player || typeof this.player.getDuration !== "function") return;
            try {
                const dur = this.player.getDuration() || 0;
                const targetTime = (percent / 100) * dur;
                this.player.seekTo(targetTime, true);
            } catch (err) {
                console.warn("Seek failed:", err);
            }
        },

        setVolume: function (val) {
            this.volume = Math.max(0, Math.min(100, Number(val)));
            if (this.isPlayerReady && this.player && typeof this.player.setVolume === "function") {
                this.player.setVolume(this.volume);
                if (this.volume === 0) {
                    this.player.mute();
                    this.isMuted = true;
                } else if (this.isMuted) {
                    this.player.unMute();
                    this.isMuted = false;
                }
            }
            this.updateVolumeUI();
        },

        toggleMute: function () {
            if (!this.isPlayerReady || !this.player) return;

            try {
                if (this.isMuted) {
                    this.player.unMute();
                    this.isMuted = false;
                    if (this.volume === 0) this.volume = 80;
                    this.player.setVolume(this.volume);
                } else {
                    this.player.mute();
                    this.isMuted = true;
                }
                this.updateVolumeUI();
            } catch (err) {
                console.warn("Mute toggle failed:", err);
            }
        },

        minimizePlayer: function () {
            if (!this.elements.nowPlayingSection) return;
            // Reserve current in-flow layout height before detaching to fixed mini-player
            this.measureAndReserveAnchorHeight();
            this.isMinimized = true;
            this.elements.nowPlayingSection.classList.add("minimized");
            this.elements.nowPlayingSection.classList.remove("docked");
            if (this.elements.expandBtn) this.elements.expandBtn.style.display = "inline-flex";
            if (this.elements.minimizeBtn) this.elements.minimizeBtn.style.display = "none";
            this.toggleQueue(false);
        },

        expandPlayer: function () {
            if (!this.elements.nowPlayingSection) return;
            this.isMinimized = false;
            this.elements.nowPlayingSection.classList.remove("minimized");
            this.elements.nowPlayingSection.classList.remove("docked");
            if (this.elements.expandBtn) this.elements.expandBtn.style.display = "none";
            if (this.elements.minimizeBtn) this.elements.minimizeBtn.style.display = "inline-flex";
            requestAnimationFrame(() => {
                this.measureAndReserveAnchorHeight();
            });
            if (this.elements.playerAnchor) {
                this.elements.playerAnchor.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        },

        closePlayer: function () {
            if (this.isPlayerReady && this.player && typeof this.player.pauseVideo === "function") {
                try {
                    this.player.pauseVideo();
                } catch (e) {}
            }
            if (this.skipTimer) {
                clearTimeout(this.skipTimer);
                this.skipTimer = null;
            }
            this.isPlaying = false;
            this.isMinimized = false;
            this.stopProgressTimer();
            this.clearActiveHighlights();

            if (this.elements.nowPlayingSection) {
                this.elements.nowPlayingSection.classList.remove("minimized");
                this.elements.nowPlayingSection.classList.remove("docked");
                this.elements.nowPlayingSection.style.display = "none";
            }
            if (this.elements.playerAnchor) {
                this.elements.playerAnchor.style.minHeight = "0";
            }
            this.lastMeasuredHeight = 0;
            if (this.elements.expandBtn) this.elements.expandBtn.style.display = "none";
            if (this.elements.minimizeBtn) this.elements.minimizeBtn.style.display = "inline-flex";
            this.toggleQueue(false);
        },

        setupScrollDocking: function () {
            const self = this;
            const checkDocking = () => {
                if (self.isMinimized || !self.elements.nowPlayingSection || !self.elements.playerAnchor) return;
                if (self.elements.nowPlayingSection.style.display === "none") return;
                if (self.currentIndex < 0) return;

                // Measure the anchor which stays in document flow at all times
                const anchorRect = self.elements.playerAnchor.getBoundingClientRect();
                // When bottom of anchor has scrolled above the viewport top
                if (anchorRect.bottom < 40) {
                    if (!self.elements.nowPlayingSection.classList.contains("docked")) {
                        self.measureAndReserveAnchorHeight();
                        self.elements.nowPlayingSection.classList.add("docked");
                        if (self.elements.expandBtn) self.elements.expandBtn.style.display = "inline-flex";
                        if (self.elements.minimizeBtn) self.elements.minimizeBtn.style.display = "none";
                    }
                } else if (anchorRect.bottom >= 40) {
                    if (self.elements.nowPlayingSection.classList.contains("docked")) {
                        self.elements.nowPlayingSection.classList.remove("docked");
                        if (self.elements.expandBtn) self.elements.expandBtn.style.display = "none";
                        if (self.elements.minimizeBtn) self.elements.minimizeBtn.style.display = "inline-flex";
                        requestAnimationFrame(() => {
                            self.measureAndReserveAnchorHeight();
                        });
                    }
                }
            };

            window.addEventListener("scroll", checkDocking, { passive: true });
            window.addEventListener("resize", () => {
                if (!self.isMinimized && self.elements.nowPlayingSection && !self.elements.nowPlayingSection.classList.contains("docked")) {
                    self.measureAndReserveAnchorHeight();
                }
            }, { passive: true });
        },

        showNowPlayingUI: function () {
            if (this.elements.nowPlayingSection) {
                this.elements.nowPlayingSection.style.display = "block";
                requestAnimationFrame(() => {
                    this.measureAndReserveAnchorHeight();
                });
            }
        },

        updateTrackMetadataUI: function (track) {
            if (this.elements.title) {
                this.elements.title.textContent = track.title || "Unknown Title";
                this.elements.title.title = track.title || "";
            }
            if (this.elements.channel) {
                this.elements.channel.textContent = track.channel_title || "YouTube";
            }
            if (this.elements.nowPlayingQuote) {
                const q = track.moodQuote || track.quote || "";
                if (q) {
                    this.elements.nowPlayingQuote.textContent = `“${q.replace(/^["“]|["”]$/g, "")}”`;
                    this.elements.nowPlayingQuote.style.display = "block";
                } else {
                    this.elements.nowPlayingQuote.style.display = "none";
                }
            }
            if (this.elements.nowPlayingMoodBadge) {
                const metaPill = document.querySelector(".song-meta-pill");
                if (metaPill) {
                    this.elements.nowPlayingMoodBadge.textContent = metaPill.textContent.trim().toUpperCase();
                }
            }
        },

        updatePlayPauseUI: function (playing) {
            if (this.elements.playIcon && this.elements.pauseIcon) {
                if (playing) {
                    this.elements.playIcon.style.display = "none";
                    this.elements.pauseIcon.style.display = "block";
                } else {
                    this.elements.playIcon.style.display = "block";
                    this.elements.pauseIcon.style.display = "none";
                }
            }
        },

        updateNavButtons: function () {
            if (this.elements.prevBtn) {
                let hasPrev = false;
                for (let i = this.currentIndex - 1; i >= 0; i--) {
                    if (this.queue[i] && !this.failedVideoIds.has(this.queue[i].video_id)) {
                        hasPrev = true;
                        break;
                    }
                }
                this.elements.prevBtn.disabled = !hasPrev;
            }
            if (this.elements.nextBtn) {
                let hasNext = false;
                for (let i = this.currentIndex + 1; i < this.queue.length; i++) {
                    if (this.queue[i] && !this.failedVideoIds.has(this.queue[i].video_id)) {
                        hasNext = true;
                        break;
                    }
                }
                this.elements.nextBtn.disabled = !hasNext;
            }
        },

        updateVolumeUI: function () {
            if (this.elements.volumeSlider) {
                this.elements.volumeSlider.value = this.isMuted ? 0 : this.volume;
            }
            if (this.elements.volIconHigh && this.elements.volIconMute) {
                if (this.isMuted || this.volume === 0) {
                    this.elements.volIconHigh.style.display = "none";
                    this.elements.volIconMute.style.display = "block";
                } else {
                    this.elements.volIconHigh.style.display = "block";
                    this.elements.volIconMute.style.display = "none";
                }
            }
        },

        showStatusMessage: function (msg, isError) {
            if (this.elements.statusText) {
                this.elements.statusText.textContent = msg;
            }
            if (this.elements.statusBadge) {
                if (isError) {
                    this.elements.statusBadge.style.color = "#ff6b6b";
                    this.elements.statusBadge.style.borderColor = "rgba(255, 107, 107, 0.4)";
                } else {
                    this.elements.statusBadge.style.color = "var(--accent-coral)";
                    this.elements.statusBadge.style.borderColor = "rgba(255, 94, 98, 0.35)";
                }
            }
        },

        startProgressTimer: function () {
            this.stopProgressTimer();
            const self = this;

            this.updateTimer = setInterval(() => {
                if (!self.isPlayerReady || !self.player || typeof self.player.getCurrentTime !== "function") return;

                try {
                    const currentTime = self.player.getCurrentTime() || 0;
                    const duration = self.player.getDuration() || 0;

                    if (!self.isUserSeeking && self.elements.progressBar && duration > 0) {
                        const pct = (currentTime / duration) * 100;
                        self.elements.progressBar.value = pct;
                    }

                    if (self.elements.currentTime) {
                        self.elements.currentTime.textContent = self.formatTime(currentTime);
                    }
                    if (self.elements.duration && duration > 0) {
                        self.elements.duration.textContent = self.formatTime(duration);
                    }
                } catch (e) {}
            }, 250);
        },

        stopProgressTimer: function () {
            if (this.updateTimer) {
                clearInterval(this.updateTimer);
                this.updateTimer = null;
            }
        },

        syncActiveTrack: function () {
            this.clearActiveHighlights();
            if (this.currentIndex < 0 || this.currentIndex >= this.queue.length) return;

            const currentTrack = this.queue[this.currentIndex];
            if (!currentTrack || !currentTrack.video_id) return;

            // Highlight corresponding music card
            const card = document.querySelector(`.music-card[data-video-id="${currentTrack.video_id}"]`);
            if (card) {
                card.classList.add("now-playing");
            }

            // Highlight corresponding queue item
            if (this.elements.queueList) {
                const item = this.elements.queueList.querySelector(`.queue-track-item[data-video-id="${currentTrack.video_id}"]`);
                if (item) {
                    item.classList.add("active-queue-item");
                }
            }
        },

        clearActiveHighlights: function () {
            document.querySelectorAll(".music-card.now-playing").forEach((c) => {
                c.classList.remove("now-playing");
            });
            if (this.elements.queueList) {
                this.elements.queueList.querySelectorAll(".active-queue-item").forEach((q) => {
                    q.classList.remove("active-queue-item");
                });
            }
        },

        // Format timing as 00:00 / 01:24 / 04:32 / 01:01:01
        formatTime: function (seconds) {
            if (isNaN(seconds) || seconds < 0) return "00:00";
            const sec = Math.floor(seconds);
            const hrs = Math.floor(sec / 3600);
            const mins = Math.floor((sec % 3600) / 60);
            const s = sec % 60;

            const padS = s < 10 ? "0" + s : String(s);
            const padM = mins < 10 ? "0" + mins : String(mins);

            if (hrs > 0) {
                const padH = hrs < 10 ? "0" + hrs : String(hrs);
                return `${padH}:${padM}:${padS}`;
            }
            return `${padM}:${padS}`;
        }
    };

    window.MoodTunePlayer = MoodTunePlayer;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => MoodTunePlayer.init());
    } else {
        MoodTunePlayer.init();
    }
})();
