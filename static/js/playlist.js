/**
 * MoodTune - Playlist Controller
 * Module 08: User Playlists & Playlist Management
 */

(function () {
    "use strict";

    // Track active target song for the Add-to-Playlist modal
    let activeTargetSong = null;

    /**
     * Escape HTML string helper to prevent XSS
     */
    function escapeHTML(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Display a floating or inline notification feedback
     */
    function showModalFeedback(modalEl, message, isError) {
        if (!modalEl) return;
        const feedbackEl = modalEl.querySelector(".modal-feedback-msg");
        if (feedbackEl) {
            feedbackEl.textContent = message;
            feedbackEl.className = "modal-feedback-msg " + (isError ? "feedback-error" : "feedback-success");
            feedbackEl.style.display = "block";
        }
    }

    function clearModalFeedback(modalEl) {
        if (!modalEl) return;
        const feedbackEl = modalEl.querySelector(".modal-feedback-msg");
        if (feedbackEl) {
            feedbackEl.textContent = "";
            feedbackEl.style.display = "none";
        }
    }

    /**
     * Modal Helpers: Open / Close
     */
    function openModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.add("active");
        modalEl.setAttribute("aria-hidden", "false");
        document.body.classList.add("modal-open");
    }

    function closeModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.remove("active");
        modalEl.setAttribute("aria-hidden", "true");
        document.body.classList.remove("modal-open");
    }

    // ============================================================
    // 1. ADD SONG TO PLAYLIST MODAL
    // ============================================================
    const addToPlaylistModal = document.getElementById("addToPlaylistModal");
    const addToPlaylistCloseBtn = document.getElementById("addToPlaylistCloseBtn");
    const closeAddToPlaylistBtn = document.getElementById("closeAddToPlaylistBtn");
    const addToPlaylistBackdrop = document.getElementById("addToPlaylistModalBackdrop");
    const modalSongTitle = document.getElementById("modalSongTitle");
    const modalSongArtist = document.getElementById("modalSongArtist");
    const playlistOptionsList = document.getElementById("playlistOptionsList");
    const quickPlaylistNameInput = document.getElementById("quickPlaylistNameInput");
    const quickCreatePlaylistBtn = document.getElementById("quickCreatePlaylistBtn");

    if (addToPlaylistCloseBtn) {
        addToPlaylistCloseBtn.addEventListener("click", () => closeModal(addToPlaylistModal));
    }
    if (closeAddToPlaylistBtn) {
        closeAddToPlaylistBtn.addEventListener("click", () => closeModal(addToPlaylistModal));
    }
    if (addToPlaylistBackdrop) {
        addToPlaylistBackdrop.addEventListener("click", () => closeModal(addToPlaylistModal));
    }

    /**
     * Fetch user's playlists and render in the Add to Playlist modal
     */
    async function loadPlaylistsForPicker() {
        if (!playlistOptionsList) return;
        playlistOptionsList.innerHTML = '<div class="playlist-loading-spinner">Loading your playlists...</div>';

        try {
            const response = await fetch("/playlists", {
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });

            if (!response.ok) {
                playlistOptionsList.innerHTML = '<p class="picker-empty-note">Could not load playlists. Please try again.</p>';
                return;
            }

            const data = await response.json();
            const playlists = data.playlists || [];

            if (playlists.length === 0) {
                playlistOptionsList.innerHTML = '<p class="picker-empty-note">You don\'t have any playlists yet. Create one below!</p>';
                return;
            }

            playlistOptionsList.innerHTML = playlists.map((p) => `
                <div class="playlist-picker-item" data-playlist-id="${p.id}" data-playlist-name="${escapeHTML(p.name)}">
                    <div class="picker-item-info">
                        <span class="picker-item-icon">🎵</span>
                        <div class="picker-item-meta">
                            <span class="picker-item-name">${escapeHTML(p.name)}</span>
                            <span class="picker-item-count">${p.song_count} ${p.song_count === 1 ? "song" : "songs"}</span>
                        </div>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm btn-pick-playlist" data-playlist-id="${p.id}">
                        <span>+ Add</span>
                    </button>
                </div>
            `).join("");

            // Attach listeners to "+ Add" buttons in the picker
            playlistOptionsList.querySelectorAll(".btn-pick-playlist").forEach((btn) => {
                btn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    const playlistId = btn.dataset.playlistId;
                    await addCurrentSongToPlaylist(playlistId, btn);
                });
            });

            // Also clicking the whole row adds the song
            playlistOptionsList.querySelectorAll(".playlist-picker-item").forEach((row) => {
                row.addEventListener("click", async () => {
                    const playlistId = row.dataset.playlistId;
                    const btn = row.querySelector(".btn-pick-playlist");
                    await addCurrentSongToPlaylist(playlistId, btn);
                });
            });

        } catch (err) {
            console.error("Error fetching playlists for picker:", err);
            playlistOptionsList.innerHTML = '<p class="picker-empty-note">Error loading playlists.</p>';
        }
    }

    /**
     * Add activeTargetSong to a specific playlist (AJAX)
     */
    async function addCurrentSongToPlaylist(playlistId, actionBtn) {
        if (!activeTargetSong || !playlistId) return;

        if (actionBtn) {
            actionBtn.setAttribute("disabled", "true");
            const span = actionBtn.querySelector("span");
            if (span) span.textContent = "Adding...";
        }

        clearModalFeedback(addToPlaylistModal);

        try {
            const response = await fetch(`/playlists/${playlistId}/add`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify(activeTargetSong)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                if (actionBtn) {
                    actionBtn.classList.remove("btn-secondary");
                    actionBtn.classList.add("btn-success-sm");
                    const span = actionBtn.querySelector("span");
                    if (span) span.textContent = "Added ✓";
                }
                showModalFeedback(addToPlaylistModal, `Added to "${data.playlist_name}"!`, false);
            } else if (response.status === 409) {
                if (actionBtn) {
                    actionBtn.removeAttribute("disabled");
                    const span = actionBtn.querySelector("span");
                    if (span) span.textContent = "In Playlist";
                }
                showModalFeedback(addToPlaylistModal, data.error || "Song is already in this playlist.", true);
            } else {
                if (actionBtn) {
                    actionBtn.removeAttribute("disabled");
                    const span = actionBtn.querySelector("span");
                    if (span) span.textContent = "+ Add";
                }
                showModalFeedback(addToPlaylistModal, data.error || "Failed to add song.", true);
            }
        } catch (err) {
            console.error("Error adding song to playlist:", err);
            if (actionBtn) {
                actionBtn.removeAttribute("disabled");
                const span = actionBtn.querySelector("span");
                if (span) span.textContent = "+ Add";
            }
            showModalFeedback(addToPlaylistModal, "Connection error. Please try again.", true);
        }
    }

    /**
     * Quick Create Playlist from inside Add modal and immediately add active song
     */
    if (quickCreatePlaylistBtn && quickPlaylistNameInput) {
        quickCreatePlaylistBtn.addEventListener("click", async () => {
            const name = quickPlaylistNameInput.value.trim();
            if (!name) {
                showModalFeedback(addToPlaylistModal, "Please enter a name for the new playlist.", true);
                quickPlaylistNameInput.focus();
                return;
            }

            quickCreatePlaylistBtn.setAttribute("disabled", "true");
            clearModalFeedback(addToPlaylistModal);

            try {
                const response = await fetch("/playlists/create", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify({ name: name })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    quickPlaylistNameInput.value = "";
                    const newPlaylistId = data.playlist.id;

                    // Immediately add the active song to this newly created playlist
                    await addCurrentSongToPlaylist(newPlaylistId, null);

                    // Refresh playlists list in picker
                    await loadPlaylistsForPicker();
                } else {
                    showModalFeedback(addToPlaylistModal, data.error || "Could not create playlist.", true);
                }
            } catch (err) {
                console.error("Error in quick create playlist:", err);
                showModalFeedback(addToPlaylistModal, "Failed to create playlist. Please try again.", true);
            } finally {
                quickCreatePlaylistBtn.removeAttribute("disabled");
            }
        });

        quickPlaylistNameInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                quickCreatePlaylistBtn.click();
            }
        });
    }

    /**
     * Public method to open Add to Playlist modal for a song
     */
    window.openAddToPlaylistModal = function (songData) {
        const moodtuneApp = document.getElementById("moodtuneApp");
        const isAuthenticated = moodtuneApp ? (moodtuneApp.dataset.authenticated === "true") : false;

        if (!isAuthenticated && !addToPlaylistModal) {
            const authModal = document.getElementById("authModal");
            if (authModal) {
                authModal.classList.add("active");
                authModal.setAttribute("aria-hidden", "false");
                document.body.classList.add("modal-open");
            } else {
                window.location.href = "/login";
            }
            return;
        }

        if (!addToPlaylistModal) return;

        activeTargetSong = songData;

        if (modalSongTitle) modalSongTitle.textContent = songData.title || "Song";
        if (modalSongArtist) modalSongArtist.textContent = songData.channel_title || "Artist";

        clearModalFeedback(addToPlaylistModal);
        if (quickPlaylistNameInput) quickPlaylistNameInput.value = "";

        openModal(addToPlaylistModal);
        loadPlaylistsForPicker();
    };

    // ============================================================
    // 2. CREATE PLAYLIST MODAL (on playlists.html)
    // ============================================================
    const createPlaylistModal = document.getElementById("createPlaylistModal");
    const openCreatePlaylistBtn = document.getElementById("openCreatePlaylistBtn");
    const emptyCreatePlaylistBtn = document.getElementById("emptyCreatePlaylistBtn");
    const createPlaylistCloseBtn = document.getElementById("createPlaylistCloseBtn");
    const cancelCreatePlaylistBtn = document.getElementById("cancelCreatePlaylistBtn");
    const createPlaylistBackdrop = document.getElementById("createPlaylistModalBackdrop");
    const createPlaylistForm = document.getElementById("createPlaylistForm");
    const playlistNameInput = document.getElementById("playlistNameInput");
    const createPlaylistError = document.getElementById("createPlaylistError");

    if (openCreatePlaylistBtn) {
        openCreatePlaylistBtn.addEventListener("click", () => {
            if (createPlaylistError) createPlaylistError.style.display = "none";
            if (playlistNameInput) playlistNameInput.value = "";
            openModal(createPlaylistModal);
            if (playlistNameInput) playlistNameInput.focus();
        });
    }
    if (emptyCreatePlaylistBtn) {
        emptyCreatePlaylistBtn.addEventListener("click", () => {
            if (createPlaylistError) createPlaylistError.style.display = "none";
            if (playlistNameInput) playlistNameInput.value = "";
            openModal(createPlaylistModal);
            if (playlistNameInput) playlistNameInput.focus();
        });
    }
    if (createPlaylistCloseBtn) {
        createPlaylistCloseBtn.addEventListener("click", () => closeModal(createPlaylistModal));
    }
    if (cancelCreatePlaylistBtn) {
        cancelCreatePlaylistBtn.addEventListener("click", () => closeModal(createPlaylistModal));
    }
    if (createPlaylistBackdrop) {
        createPlaylistBackdrop.addEventListener("click", () => closeModal(createPlaylistModal));
    }

    if (createPlaylistForm) {
        createPlaylistForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = playlistNameInput ? playlistNameInput.value.trim() : "";

            if (!name) {
                if (createPlaylistError) {
                    createPlaylistError.textContent = "Please enter a playlist name.";
                    createPlaylistError.style.display = "block";
                }
                return;
            }

            try {
                const response = await fetch("/playlists/create", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify({ name: name })
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    // Redirect to the newly created playlist's detail page
                    window.location.href = `/playlists/${data.playlist.id}`;
                } else {
                    if (createPlaylistError) {
                        createPlaylistError.textContent = data.error || "Failed to create playlist.";
                        createPlaylistError.style.display = "block";
                    }
                }
            } catch (err) {
                console.error("Error creating playlist:", err);
                if (createPlaylistError) {
                    createPlaylistError.textContent = "Connection error. Please try again.";
                    createPlaylistError.style.display = "block";
                }
            }
        });
    }

    // ============================================================
    // 3. DELETE PLAYLIST CONFIRMATION MODAL
    // ============================================================
    const deletePlaylistModal = document.getElementById("deletePlaylistModal");
    const deletePlaylistCloseBtn = document.getElementById("deletePlaylistCloseBtn");
    const cancelDeletePlaylistBtn = document.getElementById("cancelDeletePlaylistBtn");
    const deletePlaylistBackdrop = document.getElementById("deletePlaylistModalBackdrop");
    const deletePlaylistForm = document.getElementById("deletePlaylistForm");
    const deletePlaylistConfirmText = document.getElementById("deletePlaylistConfirmText");
    const deletePlaylistIdInput = document.getElementById("deletePlaylistIdInput");

    if (deletePlaylistCloseBtn) {
        deletePlaylistCloseBtn.addEventListener("click", () => closeModal(deletePlaylistModal));
    }
    if (cancelDeletePlaylistBtn) {
        cancelDeletePlaylistBtn.addEventListener("click", () => closeModal(deletePlaylistModal));
    }
    if (deletePlaylistBackdrop) {
        deletePlaylistBackdrop.addEventListener("click", () => closeModal(deletePlaylistModal));
    }

    // Wire delete buttons (using event delegation for durability)
    document.addEventListener("click", (e) => {
        const deleteTrigger = e.target.closest(".btn-delete-playlist-trigger");
        if (deleteTrigger) {
            const playlistId = deleteTrigger.dataset.playlistId;
            const playlistName = deleteTrigger.dataset.playlistName || "this playlist";

            if (deletePlaylistConfirmText) {
                deletePlaylistConfirmText.textContent = `Are you sure you want to delete "${playlistName}"? This action cannot be undone.`;
            }
            if (deletePlaylistIdInput) {
                deletePlaylistIdInput.value = playlistId;
            }
            if (deletePlaylistForm) {
                deletePlaylistForm.action = `/playlists/${playlistId}/delete`;
            }

            openModal(deletePlaylistModal);
        }
    });

    // ============================================================
    // 4. REMOVE SONG FROM PLAYLIST (on playlist_detail.html)
    // ============================================================
    document.addEventListener("click", async (e) => {
        const removeBtn = e.target.closest(".btn-remove-song");
        if (!removeBtn) return;

        const playlistId = removeBtn.dataset.playlistId;
        const songId = removeBtn.dataset.songId;
        const songTitle = removeBtn.dataset.title || "this song";

        if (!playlistId || !songId) return;

        removeBtn.setAttribute("disabled", "true");
        const originalText = removeBtn.innerHTML;
        removeBtn.innerHTML = "<span>Removing...</span>";

        try {
            const response = await fetch(`/playlists/${playlistId}/remove/${songId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            const data = await response.json();

            if (response.ok && data.success) {
                const songRow = document.getElementById(`playlistSongRow-${songId}`);
                if (songRow) {
                    songRow.style.transition = "opacity 0.3s ease, transform 0.3s ease";
                    songRow.style.opacity = "0";
                    songRow.style.transform = "translateX(20px)";
                    setTimeout(() => {
                        songRow.remove();

                        // Update song count in detail header
                        const countPill = document.getElementById("detailSongCountPill");
                        const remainingRows = document.querySelectorAll("#playlistSongsGrid .music-song-row");
                        const newCount = remainingRows.length;

                        if (countPill) {
                            countPill.textContent = `${newCount} ${newCount === 1 ? "Song" : "Songs"}`;
                        }

                        // Re-index remaining rows (01, 02, ...)
                        remainingRows.forEach((row, idx) => {
                            const indexEl = row.querySelector(".song-row-index");
                            if (indexEl) {
                                indexEl.textContent = String(idx + 1).padStart(2, "0");
                            }
                            const metaPill = row.querySelector(".song-meta-pill");
                            if (metaPill) {
                                metaPill.textContent = `Track ${idx + 1}`;
                            }
                            row.dataset.index = idx;
                            const playBtn = row.querySelector(".btn-play-song");
                            if (playBtn) playBtn.dataset.index = idx;
                        });

                        // If empty, show empty notice and hide Play All
                        if (newCount === 0) {
                            const detailPlayAllBtn = document.getElementById("detailPlayAllBtn");
                            if (detailPlayAllBtn) detailPlayAllBtn.style.display = "none";

                            const songsGrid = document.getElementById("playlistSongsGrid");
                            if (songsGrid) {
                                songsGrid.innerHTML = `
                                    <div class="playlist-empty-songs glass-panel" id="playlistEmptySongsNotice">
                                        <div class="empty-icon">🎵</div>
                                        <h3 class="empty-title">This playlist is currently empty</h3>
                                        <p class="empty-desc">Discover music using AI or manual search on the home page and click <strong>+ Playlist</strong> to add songs here.</p>
                                        <a href="/" class="btn btn-primary btn-sm">
                                            <span>Go to Music Discovery</span>
                                        </a>
                                    </div>
                                `;
                            }
                        }
                    }, 300);
                }
            } else {
                alert(data.error || "Failed to remove song.");
                removeBtn.removeAttribute("disabled");
                removeBtn.innerHTML = originalText;
            }
        } catch (err) {
            console.error("Error removing song from playlist:", err);
            removeBtn.removeAttribute("disabled");
            removeBtn.innerHTML = originalText;
        }
    });

    // ============================================================
    // 5. PLAY ALL PLAYLIST SONGS TRIGGER
    // ============================================================
    document.addEventListener("click", async (e) => {
        const playAllBtn = e.target.closest(".btn-play-all-playlist");
        if (!playAllBtn) return;

        const playlistId = playAllBtn.dataset.playlistId;
        if (!playlistId) return;

        // Check if songs are already present in the current DOM (e.g. on playlist_detail.html)
        const songsGrid = document.getElementById("playlistSongsGrid");
        if (songsGrid && songsGrid.dataset.playlistId === playlistId) {
            const rows = songsGrid.querySelectorAll(".music-song-row");
            const videos = [];
            rows.forEach((row) => {
                const vid = row.dataset.videoId;
                if (vid) {
                    videos.push({
                        video_id: vid,
                        title: row.dataset.title || row.querySelector(".song-row-title")?.textContent?.trim() || "Track",
                        channel_title: row.dataset.channelTitle || row.querySelector(".song-meta-channel span")?.textContent?.trim() || "Artist",
                        thumbnail: row.dataset.thumbnail || "",
                        youtube_url: row.dataset.youtubeUrl || `https://www.youtube.com/watch?v=${vid}`
                    });
                }
            });

            if (videos.length > 0 && window.MoodTunePlayer) {
                window.MoodTunePlayer.setQueue(videos);
                window.MoodTunePlayer.playSong(videos[0].video_id, 0);
            }
            return;
        }

        // Otherwise (e.g. clicked Play All from playlists.html grid), fetch songs via AJAX
        playAllBtn.setAttribute("disabled", "true");
        const span = playAllBtn.querySelector("span");
        const originalText = span ? span.textContent : "Play All";
        if (span) span.textContent = "Loading...";

        try {
            const response = await fetch(`/playlists/${playlistId}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });

            const data = await response.json();

            if (response.ok && data.success && data.playlist && data.playlist.songs) {
                const songs = data.playlist.songs;
                if (songs.length > 0 && window.MoodTunePlayer) {
                    window.MoodTunePlayer.setQueue(songs);
                    window.MoodTunePlayer.playSong(songs[0].video_id, 0);
                }
            } else {
                alert(data.error || "Could not load playlist tracks.");
            }
        } catch (err) {
            console.error("Error playing all playlist songs:", err);
        } finally {
            playAllBtn.removeAttribute("disabled");
            if (span) span.textContent = originalText;
        }
    });

    // ============================================================
    // 6. GLOBAL DELEGATED "+ PLAYLIST" BUTTON HANDLER
    // ============================================================
    document.addEventListener("click", (e) => {
        const addBtn = e.target.closest(".btn-add-to-playlist");
        if (!addBtn) return;

        // Try to get data directly from the button or its parent card
        const card = addBtn.closest(".music-card");
        const videoId = addBtn.dataset.videoId || (card ? card.dataset.videoId : null);
        const title = addBtn.dataset.title || (card ? card.dataset.title : null) || (card ? card.querySelector(".song-row-title")?.textContent?.trim() : "Track");
        const channelTitle = addBtn.dataset.channelTitle || (card ? card.dataset.channelTitle : null) || (card ? card.querySelector(".song-meta-channel span")?.textContent?.trim() : "Artist");
        const thumbnail = addBtn.dataset.thumbnail || (card ? card.dataset.thumbnail : null) || "";
        const youtubeUrl = addBtn.dataset.youtubeUrl || (card ? card.dataset.youtubeUrl : null) || `https://www.youtube.com/watch?v=${videoId}`;

        if (!videoId) return;

        const songData = {
            video_id: videoId,
            title: title || "Song",
            channel_title: channelTitle || "Artist",
            thumbnail: thumbnail,
            youtube_url: youtubeUrl
        };

        window.openAddToPlaylistModal(songData);
    });

    // Global escape key to close any active playlist modal
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (addToPlaylistModal && addToPlaylistModal.classList.contains("active")) {
                closeModal(addToPlaylistModal);
            }
            if (createPlaylistModal && createPlaylistModal.classList.contains("active")) {
                closeModal(createPlaylistModal);
            }
            if (deletePlaylistModal && deletePlaylistModal.classList.contains("active")) {
                closeModal(deletePlaylistModal);
            }
        }
    });

})();
