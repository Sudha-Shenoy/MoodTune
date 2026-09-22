/**
 * MoodTune - Client-Side JavaScript
 * Module 04: Authentication-Gated Mood & Language Selection
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Determine Authentication & Initial Preference State
    const moodtuneApp = document.getElementById("moodtuneApp");
    const isAuthenticated = moodtuneApp ? (moodtuneApp.dataset.authenticated === "true") : false;

    let currentMood = moodtuneApp ? (moodtuneApp.dataset.selectedMood || "") : "";
    let currentLang = moodtuneApp ? (moodtuneApp.dataset.selectedLanguage || "") : "";

    // 2. Authentication Gate Modal Elements & Controllers
    const authModal = document.getElementById("authModal");
    const authModalBackdrop = document.getElementById("authModalBackdrop");
    const authModalCloseBtn = document.getElementById("authModalCloseBtn");
    const authModalLaterBtn = document.getElementById("authModalLaterBtn");

    function openAuthModal() {
        if (authModal) {
            authModal.classList.add("active");
            authModal.setAttribute("aria-hidden", "false");
            document.body.classList.add("modal-open");
        }
    }

    function closeAuthModal() {
        if (authModal) {
            authModal.classList.remove("active");
            authModal.setAttribute("aria-hidden", "true");
            document.body.classList.remove("modal-open");
        }
    }

    if (authModalCloseBtn) authModalCloseBtn.addEventListener("click", closeAuthModal);
    if (authModalLaterBtn) authModalLaterBtn.addEventListener("click", closeAuthModal);
    if (authModalBackdrop) authModalBackdrop.addEventListener("click", closeAuthModal);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && authModal && authModal.classList.contains("active")) {
            closeAuthModal();
        }
    });

    // 3. Selection Summary Action Bar Elements & Update Logic
    const summaryMoodDisplay = document.getElementById("summaryMoodDisplay");
    const summaryLangDisplay = document.getElementById("summaryLangDisplay");
    const findMusicBtn = document.getElementById("findMusicBtn");
    const selectionStatusMsg = document.getElementById("selectionStatusMsg");

    function updateSummaryUI() {
        if (summaryMoodDisplay) {
            summaryMoodDisplay.textContent = currentMood || "None";
        }
        if (summaryLangDisplay) {
            summaryLangDisplay.textContent = currentLang || "None";
        }
        if (findMusicBtn) {
            if (currentMood && currentLang) {
                findMusicBtn.removeAttribute("disabled");
                if (selectionStatusMsg) {
                    selectionStatusMsg.textContent = "Both preferences selected. Click Find My Music to proceed.";
                }
            } else {
                findMusicBtn.setAttribute("disabled", "true");
                if (selectionStatusMsg) {
                    if (isAuthenticated) {
                        selectionStatusMsg.textContent = "Select one mood and one language to personalize playback.";
                    } else {
                        selectionStatusMsg.textContent = "Sign in to unlock personalized music matching.";
                    }
                }
            }
        }
    }

    async function sendPreferences(payload) {
        try {
            const response = await fetch("/preferences", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify(payload)
            });

            if (response.status === 401) {
                openAuthModal();
                return false;
            }

            const data = await response.json();
            if (response.ok && data.success) {
                if (data.selected_mood) currentMood = data.selected_mood;
                if (data.selected_language) currentLang = data.selected_language;
                updateSummaryUI();
                return true;
            } else {
                console.error("Failed to save preference:", data.error);
                return false;
            }
        } catch (err) {
            console.error("Error communicating with preferences endpoint:", err);
            return false;
        }
    }

    // 4. Mood Card Selection (Authentication Gated)
    const moodCards = document.querySelectorAll(".mood-card");
    moodCards.forEach((card) => {
        function handleMoodSelect() {
            if (!isAuthenticated) {
                openAuthModal();
                return;
            }

            const mood = card.dataset.mood;
            if (!mood) return;

            // Single mood selection
            moodCards.forEach((c) => c.classList.remove("active"));
            card.classList.add("active");
            currentMood = mood;
            updateSummaryUI();
            sendPreferences({ mood: mood });
        }

        card.addEventListener("click", handleMoodSelect);

        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                handleMoodSelect();
            }
        });
    });

    // 5. Language Pill Selection (Authentication Gated)
    const langPills = document.querySelectorAll(".lang-pill");
    langPills.forEach((pill) => {
        pill.addEventListener("click", () => {
            if (!isAuthenticated) {
                openAuthModal();
                return;
            }

            const lang = pill.dataset.lang;
            if (!lang) return;

            // Single language selection
            langPills.forEach((p) => p.classList.remove("active"));
            pill.classList.add("active");
            currentLang = lang;
            updateSummaryUI();
            sendPreferences({ language: lang });
        });
    });

    // Mood Artwork and Fallback Quotes System
    const FALLBACK_QUOTES = {
        Sad: [
            "Some melodies understand the silence better than words.",
            "Let the quiet strings echo the thoughts you cannot speak.",
            "In the stillness of sound, the heart finds its honest voice.",
            "A tender melody for the solitary hours of reflection.",
            "Gentle chords that accompany the rain within.",
            "Memories drift like gentle notes on an evening breeze.",
            "Music is the quiet companion of a searching soul.",
            "When words fall short, the harmony holds the space.",
            "A soft cadence to soothe a heavy heart.",
            "Echoes of longing woven into timeless acoustic notes."
        ],
        Happy: [
            "Bright rhythms that instantly lift your spirit to the sky.",
            "Pure sonic sunshine for a radiant state of mind.",
            "Let the joy in every chord light up your day.",
            "An infectious tempo of pure positive vibrations.",
            "Celebrate the simple happiness of right now.",
            "Golden melodies that make your soul smile.",
            "Dance to the bright beat of an uplifting moment.",
            "Every rhythm brings a fresh spark of optimism.",
            "A burst of musical sunlight through every melody.",
            "Joyful chords for an unforgettable, cheerful day."
        ],
        Chill: [
            "Slow down. Let the music carry the weight of the moment.",
            "Unwind and let the smooth frequencies settle in.",
            "Soft acoustics for an unhurried, peaceful state of mind.",
            "Breathe in peace, exhale tension to the tempo.",
            "Mellow beats for quiet corners and twilight thoughts.",
            "Let the tempo drift gently like clouds across the sky.",
            "A calming pulse to ease your thoughts into tranquility.",
            "Gentle soundscapes for resting your mind.",
            "Subtle chords designed for late night serenity.",
            "Peaceful vibrations that turn the noise into calm."
        ],
        Romantic: [
            "Some feelings sound sweeter when they become a melody.",
            "A heartfelt cadence where every lyric feels intimate.",
            "Warm acoustic melodies that speak directly to the heart.",
            "Two souls dancing in harmony with the rhythm.",
            "A tender frequency designed for romantic evenings.",
            "Let every chord remind you of a beautiful memory.",
            "Soft harmonies that whisper what love cannot write.",
            "A soundtrack for shared glances and gentle warmth.",
            "Love is a melody that echoes long after the music ends.",
            "Warm strings and sweet cadences woven with devotion."
        ],
        Relaxed: [
            "Peaceful ambient tones that wash away the day's noise.",
            "Serenity captured in delicate musical frequencies.",
            "Calm waves of soothing acoustic harmony.",
            "Let the soothing rhythm steady your breathing.",
            "A gentle sanctuary crafted out of quiet notes.",
            "Rest your mind within the warmth of smooth melodies.",
            "Stillness made audible through peaceful soundscapes.",
            "Unclutter your day with soft, tranquil vibrations.",
            "A mindful interlude of serene relaxation.",
            "Gentle acoustic warmth that cradles the evening."
        ],
        Energetic: [
            "Feel the electric pulse and let the bass fuel your fire.",
            "High-octane soundscapes built for unstoppable drive.",
            "Turn up the volume and charge your spirit with power.",
            "Unleash pure momentum with every rising beat.",
            "A rush of adrenaline surging through every track.",
            "Feel the sonic velocity pushing you forward.",
            "Electric frequencies designed to ignite your energy.",
            "Explosive rhythms that demand you move.",
            "High voltage tempo for peak performance and thrill.",
            "Unstoppable energy woven into heavy basslines."
        ],
        Motivated: [
            "Every beat is another step forward towards your summit.",
            "Rise above the doubts with conviction in every note.",
            "Determination set to an unstoppable, driving rhythm.",
            "Turn ambition into action with powerful musical cues.",
            "Focus your mind and conquer the challenge ahead.",
            "A triumphant anthem for those who refuse to stop.",
            "Strength and grit distilled into driving percussion.",
            "Let the melody remind you of the strength you carry.",
            "Unwavering focus powered by an energetic cadence.",
            "Your journey, your triumph, scored by epic sound."
        ],
        Party: [
            "Celebrate the night with beats that never stop moving.",
            "Electrifying rhythms made for losing track of time.",
            "Turn the room into a festival of pure sound.",
            "Feel the bass vibrate through the entire dance floor.",
            "Unfiltered celebration captured in high-tempo grooves.",
            "Drop the beat and let the good times take over.",
            "Loud, proud, and unapologetically festive music.",
            "Non-stop dance energy from the first note to the last.",
            "A celebration of rhythm, friends, and late night memories.",
            "Electric party vibes that keep the night alive."
        ]
    };

    function getClientFallbackQuotes(mood) {
        return FALLBACK_QUOTES[mood] || FALLBACK_QUOTES["Chill"];
    }

    function generateMoodArtwork(mood, index) {
        const normalizedMood = (mood || "Chill").trim();
        const moodKey = normalizedMood.toLowerCase();
        const moodIcons = {
            sad: "🌧️",
            happy: "☀️",
            chill: "🌙",
            romantic: "✨",
            relaxed: "🍃",
            energetic: "⚡",
            motivated: "🏔️",
            party: "🎉"
        };
        const icon = moodIcons[moodKey] || "🎵";

        return `
            <div class="mood-artwork-box mood-art-${escapeHTML(moodKey)}" data-mood="${escapeHTML(normalizedMood)}">
                <span class="mood-art-icon" aria-hidden="true">${icon}</span>
                <div class="card-now-playing-badge" aria-hidden="true">
                    <span class="equalizer-bars-mini">
                        <span class="eq-bar"></span>
                        <span class="eq-bar"></span>
                        <span class="eq-bar"></span>
                        <span class="eq-bar"></span>
                    </span>
                </div>
            </div>
        `;
    }

    // Helper to safely escape text for HTML insertion
    function escapeHTML(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    // 6. "Find My Music" Action Button (AI Recommendation Engine Trigger)
    const aiLoadingIndicator = document.getElementById("aiLoadingIndicator");
    const aiRecommendationCard = document.getElementById("aiRecommendationCard");
    const aiVibeTitle = document.getElementById("aiVibeTitle");
    const aiStylePills = document.getElementById("aiStylePills");
    const aiDescText = document.getElementById("aiDescText");
    const aiQueryPills = document.getElementById("aiQueryPills");

    if (findMusicBtn) {
        findMusicBtn.addEventListener("click", async () => {
            if (!isAuthenticated) {
                openAuthModal();
                return;
            }

            if (!currentMood || !currentLang) {
                if (selectionStatusMsg) {
                    selectionStatusMsg.textContent = "Please select both a mood and language first.";
                }
                return;
            }

            // 1. Enter AI Loading State
            if (aiLoadingIndicator) {
                aiLoadingIndicator.style.display = "block";
            }
            if (aiRecommendationCard) {
                aiRecommendationCard.style.display = "none";
            }

            findMusicBtn.setAttribute("disabled", "true");
            const btnSpan = findMusicBtn.querySelector("span");
            const originalBtnText = btnSpan ? btnSpan.textContent : "Find My Music";
            if (btnSpan) btnSpan.textContent = "Analyzing Vibe...";

            if (selectionStatusMsg) {
                selectionStatusMsg.textContent = "MoodTune AI is curating your personalized soundscape...";
            }

            // Smooth scroll to loading indicator
            if (aiLoadingIndicator) {
                aiLoadingIndicator.scrollIntoView({ behavior: "smooth", block: "center" });
            }

            try {
                const response = await fetch("/generate-recommendation", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                if (response.status === 401) {
                    if (aiLoadingIndicator) aiLoadingIndicator.style.display = "none";
                    openAuthModal();
                    return;
                }

                const data = await response.json();

                if (!response.ok || !data.success) {
                    if (aiLoadingIndicator) aiLoadingIndicator.style.display = "none";
                    const errorMsg = data.error || "Sorry, MoodTune couldn't create your recommendation right now. Please try again.";
                    if (selectionStatusMsg) {
                        selectionStatusMsg.textContent = errorMsg;
                    }
                    return;
                }

                // 2. Successfully Generated: Populate & Reveal Recommendation Card
                const rec = data.recommendation;

                if (aiVibeTitle) {
                    aiVibeTitle.textContent = `${rec.mood} • ${rec.language}`;
                }

                if (aiStylePills && Array.isArray(rec.music_style)) {
                    aiStylePills.innerHTML = rec.music_style
                        .map((style) => `<span class="style-pill">${escapeHTML(style)}</span>`)
                        .join("");
                }

                if (aiDescText) {
                    aiDescText.textContent = rec.description;
                }

                if (aiQueryPills && Array.isArray(rec.search_queries)) {
                    aiQueryPills.innerHTML = rec.search_queries
                        .map((query) => `<span class="query-pill"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg><span>${escapeHTML(query)}</span></span>`)
                        .join("");
                }

                if (aiLoadingIndicator) {
                    aiLoadingIndicator.style.display = "none";
                }

                if (aiRecommendationCard) {
                    aiRecommendationCard.style.display = "block";
                    aiRecommendationCard.scrollIntoView({ behavior: "smooth", block: "center" });
                }

                if (selectionStatusMsg) {
                    selectionStatusMsg.textContent = "✨ AI vibe generated! Click 'Discover Songs' to fetch real music.";
                }

                // Enable the Discover Songs button in AI card footer
                const exploreMusicBtn = document.getElementById("exploreMusicBtn");
                if (exploreMusicBtn) {
                    exploreMusicBtn.removeAttribute("disabled");
                }

                if (btnSpan) btnSpan.textContent = "Regenerate Vibe";
            } catch (err) {
                console.error("Error generating AI recommendation:", err);
                if (aiLoadingIndicator) aiLoadingIndicator.style.display = "none";
                if (selectionStatusMsg) {
                    selectionStatusMsg.textContent = "Sorry, MoodTune couldn't create your recommendation right now. Please try again.";
                }
                if (btnSpan) btnSpan.textContent = originalBtnText;
            } finally {
                findMusicBtn.removeAttribute("disabled");
            }
        });
    }

    // 7. YouTube Music Discovery (Module 06)
    const exploreMusicBtn = document.getElementById("exploreMusicBtn");
    const youtubeResultsSection = document.getElementById("youtubeResultsSection");
    const youtubeLoadingIndicator = document.getElementById("youtubeLoadingIndicator");
    const youtubeResultsGrid = document.getElementById("youtubeResultsGrid");
    const youtubeErrorBanner = document.getElementById("youtubeErrorBanner");
    const youtubeErrorText = document.getElementById("youtubeErrorText");
    const youtubeEmptyState = document.getElementById("youtubeEmptyState");

    if (exploreMusicBtn) {
        exploreMusicBtn.addEventListener("click", async () => {
            // Guard: Check authentication using existing Module 04 state
            if (!isAuthenticated) {
                openAuthModal();
                return;
            }

            const btnSpan = exploreMusicBtn.querySelector("span");
            const originalBtnText = btnSpan ? btnSpan.textContent : "Discover Songs";
            if (btnSpan) btnSpan.textContent = "Searching YouTube...";
            exploreMusicBtn.setAttribute("disabled", "true");

            // Reveal section and show loading state
            if (youtubeResultsSection) youtubeResultsSection.style.display = "block";
            if (youtubeLoadingIndicator) youtubeLoadingIndicator.style.display = "block";
            if (youtubeErrorBanner) youtubeErrorBanner.style.display = "none";
            if (youtubeEmptyState) youtubeEmptyState.style.display = "none";

            if (youtubeResultsSection) {
                youtubeResultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
            }

            try {
                const response = await fetch("/search-music", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });

                if (response.status === 401) {
                    if (youtubeLoadingIndicator) youtubeLoadingIndicator.style.display = "none";
                    openAuthModal();
                    return;
                }

                const data = await response.json();

                if (youtubeLoadingIndicator) {
                    youtubeLoadingIndicator.style.display = "none";
                }

                if (!response.ok || !data.success) {
                    const errorMsg = data.error || "MoodTune couldn't load music right now. Please try again.";
                    if (youtubeErrorText) youtubeErrorText.textContent = errorMsg;
                    if (youtubeErrorBanner) youtubeErrorBanner.style.display = "flex";
                    return;
                }

                const videos = data.videos || [];
                if (videos.length === 0) {
                    if (youtubeResultsGrid) {
                        youtubeResultsGrid.innerHTML = "";
                        youtubeResultsGrid.style.display = "none";
                    }
                    if (youtubeEmptyState) youtubeEmptyState.style.display = "block";
                } else {
                    if (youtubeEmptyState) youtubeEmptyState.style.display = "none";

                    // Update Mix Hero Banner
                    const mixHeroTitle = document.getElementById("mixHeroTitle");
                    if (mixHeroTitle && currentMood && currentLang) {
                        mixHeroTitle.textContent = `Your ${currentMood} ${currentLang} Mix`;
                    }

                    const collectionCountPill = document.getElementById("collectionCountPill");
                    if (collectionCountPill) {
                        collectionCountPill.textContent = `${videos.length} Songs`;
                    }

                    const mixHeroCountBadge = document.getElementById("mixHeroCountBadge");
                    if (mixHeroCountBadge) {
                        mixHeroCountBadge.textContent = `${videos.length} songs selected for your vibe`;
                    }

                    // Update AI description and style tags in hero if present
                    const aiDescTextEl = document.getElementById("aiDescText");
                    const mixHeroDescTextEl = document.getElementById("mixHeroDescText");
                    if (mixHeroDescTextEl && aiDescTextEl && aiDescTextEl.textContent.trim()) {
                        mixHeroDescTextEl.textContent = aiDescTextEl.textContent.trim();
                    }

                    const aiStylePillsEl = document.getElementById("aiStylePills");
                    const mixHeroStyleTagsEl = document.getElementById("mixHeroStyleTags");
                    if (mixHeroStyleTagsEl && aiStylePillsEl) {
                        const pills = aiStylePillsEl.querySelectorAll(".style-pill");
                        if (pills.length > 0) {
                            mixHeroStyleTagsEl.innerHTML = Array.from(pills)
                                .map((p) => `<span class="mix-style-tag">${escapeHTML(p.textContent.trim())}</span>`)
                                .join("");
                        }
                    }

                    const moodQuotes = (data.mood_quotes && Array.isArray(data.mood_quotes) && data.mood_quotes.length > 0)
                        ? data.mood_quotes
                        : getClientFallbackQuotes(currentMood);

                    if (youtubeResultsGrid) {
                        youtubeResultsGrid.innerHTML = videos.map((video, idx) => {
                            const quote = moodQuotes[idx % moodQuotes.length];
                            return `
                                <div class="music-card music-song-row glass-panel" data-video-id="${escapeHTML(video.video_id)}" data-index="${idx}">
                                    <!-- Mood Artwork (pure CSS/SVG based on mood, no YouTube thumbnail dominating) -->
                                    <div class="song-row-art-wrap">
                                        ${generateMoodArtwork(currentMood, idx)}
                                    </div>

                                    <!-- Song Info & AI Mood Quote -->
                                    <div class="song-row-info">
                                        <div class="song-row-title-row">
                                            <span class="song-row-index">${String(idx + 1).padStart(2, "0")}</span>
                                            <h4 class="music-card-title song-row-title" title="${escapeHTML(video.title)}">${escapeHTML(video.title)}</h4>
                                        </div>
                                        <p class="song-row-quote">“${escapeHTML(quote)}”</p>
                                        <div class="song-row-meta">
                                            <span class="song-meta-pill">${escapeHTML(currentLang)} • ${escapeHTML(currentMood)}</span>
                                            <span class="music-card-channel song-meta-channel">
                                                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
                                                    <path d="M9 18V5l12-2v13"></path>
                                                    <circle cx="6" cy="18" r="3"></circle>
                                                    <circle cx="18" cy="16" r="3"></circle>
                                                </svg>
                                                <span>${escapeHTML(video.channel_title)}</span>
                                            </span>
                                        </div>
                                    </div>

                                    <!-- Actions: Primary Play, Secondary Watch on YouTube -->
                                    <div class="song-row-actions music-card-actions">
                                        <button type="button" class="btn btn-primary btn-play-song" data-video-id="${escapeHTML(video.video_id)}" data-index="${idx}" aria-label="Play ${escapeHTML(video.title)}">
                                            <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
                                                <polygon points="5 3 19 12 5 21 5 3"></polygon>
                                            </svg>
                                            <span class="btn-play-label">Play</span>
                                        </button>
                                        <a href="${escapeHTML(video.youtube_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-youtube-watch" aria-label="Watch ${escapeHTML(video.title)} on YouTube" title="Watch on YouTube">
                                            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                                                <polygon points="5 3 19 12 5 21 5 3"></polygon>
                                            </svg>
                                            <span>Watch on YouTube</span>
                                        </a>
                                    </div>
                                </div>
                            `;
                        }).join("");
                        youtubeResultsGrid.style.display = "flex";

                        // Update Module 07 Music Player queue with fresh songs and mood quotes
                        if (window.MoodTunePlayer && typeof window.MoodTunePlayer.setQueue === "function") {
                            window.MoodTunePlayer.setQueue(videos, moodQuotes);
                        }
                    }
                }

                if (btnSpan) btnSpan.textContent = "Refresh Songs";
            } catch (err) {
                console.error("Error discovering YouTube music:", err);
                if (youtubeLoadingIndicator) youtubeLoadingIndicator.style.display = "none";
                if (youtubeErrorText) {
                    youtubeErrorText.textContent = "Network connection failed. Please check your connection and try again.";
                }
                if (youtubeErrorBanner) youtubeErrorBanner.style.display = "flex";
                if (btnSpan) btnSpan.textContent = originalBtnText;
            } finally {
                exploreMusicBtn.removeAttribute("disabled");
            }
        });
    }

    // 8. Mobile Navigation Toggle
    const mobileMenuToggle = document.getElementById("mobileMenuToggle");
    const navLinks = document.getElementById("navLinks");

    if (mobileMenuToggle && navLinks) {
        mobileMenuToggle.addEventListener("click", () => {
            const isExpanded = mobileMenuToggle.getAttribute("aria-expanded") === "true";
            mobileMenuToggle.setAttribute("aria-expanded", String(!isExpanded));
            navLinks.classList.toggle("open");
        });

        // Close mobile menu when clicking any nav link
        navLinks.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", () => {
                if (navLinks.classList.contains("open")) {
                    navLinks.classList.remove("open");
                    mobileMenuToggle.setAttribute("aria-expanded", "false");
                }
            });
        });
    }

    // 8. Floating Music Player - Play / Pause Visual Toggle
    const previewPlayBtn = document.getElementById("previewPlayBtn");
    const equalizerWrapper = document.querySelector(".equalizer-wrapper");

    if (previewPlayBtn && equalizerWrapper) {
        const playIcon = previewPlayBtn.querySelector(".play-icon");
        const pauseIcon = previewPlayBtn.querySelector(".pause-icon");

        previewPlayBtn.addEventListener("click", () => {
            const isPaused = equalizerWrapper.classList.toggle("paused");

            if (playIcon && pauseIcon) {
                if (isPaused) {
                    playIcon.classList.remove("hidden");
                    pauseIcon.classList.add("hidden");
                    previewPlayBtn.setAttribute("aria-label", "Resume visual equalizer animation");
                } else {
                    playIcon.classList.add("hidden");
                    pauseIcon.classList.remove("hidden");
                    previewPlayBtn.setAttribute("aria-label", "Pause visual equalizer animation");
                }
            }
        });
    }

    // 9. Smooth Scroll for Internal Anchor Links
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener("click", (event) => {
            const targetId = anchor.getAttribute("href");
            if (targetId && targetId !== "#" && targetId.length > 1) {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    event.preventDefault();
                    targetElement.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                }
            }
        });
    });

    // Initialize summary UI state on page load
    updateSummaryUI();
});
