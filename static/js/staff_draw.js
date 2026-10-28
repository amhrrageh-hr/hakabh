/* staff_draw.js - محرك إدارة القرعة والسحوبات - مستخرج تلقائياً */

// --- Manager Only: Complete Draw Management Engine (Desktop Qt Emulation) ---
        let drawState = {
            activeSubTab: 'draw-run-view',
            selectedDrawType: 'القرعة الاسبوعية',
            selectedCategory: 'الكل',
            currentCandidates: [],
            currentExcluded: [],
            currentWinners: [],
            categoriesStats: [],
            settings: {},
            lastPerformedWinner: null,
            winnersSearchTimer: null,
            excludedSearchTimer: null
        };

        function showDrawAlert(message, type = 'info') {
            const box = document.getElementById('draw-alert-box');
            if (!box) return;
            box.textContent = message;
            box.className = 'alert ' + (type === 'success' ? 'alert-success' : type === 'info' ? 'alert-info' : 'alert-danger');
            box.style.display = 'block';
            setTimeout(() => {
                if (box) box.style.display = 'none';
            }, 6000);
        }

        // Sub-Tab Switching
        function switchDrawSubTab(viewId, btn) {
            document.querySelectorAll('.draw-subtab-view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.draw-subtab-btn').forEach(b => b.classList.remove('active'));
            const targetView = document.getElementById(viewId);
            if (targetView) targetView.classList.add('active');
            if (btn) btn.classList.add('active');
            drawState.activeSubTab = viewId;
        }

        // 1. --- Category Statistics & Action Cards Loading ---
        async function loadAllDrawStats(showPrompt = false) {
            try {
                // Fetch Category Statistics summary
                const statsRes = await fetch('/api/v1/draw/stats');
                if (statsRes.ok) {
                    const statsData = await statsRes.json();
                    drawState.categoriesStats = statsData.categories || [];
                    renderCategoryStatsCards(drawState.categoriesStats);
                }

                // Fetch candidates counts for the 3 draw types
                await updateDrawCardCounts();

                // Fetch candidates for current filter
                await loadCandidatesList();

                if (showPrompt) {
                    showDrawAlert("تم تحديث إحصائيات السحب والتأهل بنجاح.", "success");
                }
            } catch (err) {
                console.error("Load draw stats error:", err);
                showDrawAlert("تعذر تحديث إحصائيات السحب من الخادم.", "danger");
            }
        }

        function renderCategoryStatsCards(categories) {
            const container = document.getElementById('categories-stats-cards');
            if (!container) return;

            if (!categories || categories.length === 0) {
                container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #94a3b8; padding: 15px; font-size: 0.82rem;">لا توجد فئات مسجلة حالياً.</div>';
                return;
            }

            container.innerHTML = categories.map(c => `
                <div class="cat-stat-card">
                    <div class="cat-stat-header">
                        <span>📊 ${c.category_name}</span>
                        <span style="font-size: 0.72rem; color: #64748b; font-weight: normal;">(دورة ${c.active_cycle || 1} من ${c.total_cycles || 1})</span>
                    </div>
                    <div class="cat-stat-boxes">
                        <div class="mini-stat-box" style="border: 1px solid #dcfce7;">
                            <div class="mini-stat-val text-green">${c.completed_cycle_count}</div>
                            <div class="mini-stat-lbl">أتموا الدورة 🎯</div>
                        </div>
                        <div class="mini-stat-box" style="border: 1px solid #dbeafe;">
                            <div class="mini-stat-val text-blue">${c.incentive_count}</div>
                            <div class="mini-stat-lbl">مؤهلين التحفيزية ⭐</div>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        async function updateDrawCardCounts() {
            const cat = drawState.selectedCategory;
            const catParam = cat === 'الكل' ? '' : `&category=${encodeURIComponent(cat)}`;

            try {
                // Fetch weekly candidates count
                const [weeklyRes, incentiveRes, grandRes] = await Promise.all([
                    fetch(`/api/v1/draw/candidates?draw_type=${encodeURIComponent('القرعة الاسبوعية')}${catParam}`),
                    fetch(`/api/v1/draw/candidates?draw_type=${encodeURIComponent('الجائزة التحفيزية')}${catParam}`),
                    fetch(`/api/v1/draw/candidates?draw_type=${encodeURIComponent('الجائزة الكبرى')}${catParam}`)
                ]);

                const weeklyList = weeklyRes.ok ? await weeklyRes.json() : [];
                const incentiveList = incentiveRes.ok ? await incentiveRes.json() : [];
                const grandList = grandRes.ok ? await grandRes.json() : [];

                document.getElementById('card-weekly-count').textContent = weeklyList.length;
                document.getElementById('card-incentive-count').textContent = incentiveList.length;
                document.getElementById('card-grand-count').textContent = grandList.length;
            } catch (e) {
                console.error("Update draw card counts error:", e);
            }
        }

        async function loadCandidatesList() {
            const cat = drawState.selectedCategory;
            const drawType = drawState.selectedDrawType || 'القرعة الاسبوعية';
            const catParam = cat === 'الكل' ? '' : `&category=${encodeURIComponent(cat)}`;

            try {
                const res = await fetch(`/api/v1/draw/candidates?draw_type=${encodeURIComponent(drawType)}${catParam}`);
                if (res.ok) {
                    drawState.currentCandidates = await res.json();
                } else {
                    drawState.currentCandidates = [];
                }
                document.getElementById('count-cand-badge').textContent = drawState.currentCandidates.length;
                renderCandidatesTable(drawState.currentCandidates);
            } catch (e) {
                console.error("Load candidates error:", e);
            }
        }

        function renderCandidatesTable(items) {
            const tbody = document.getElementById('candidates-tbody');
            if (!tbody) return;

            if (!items || items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #94a3b8; padding: 18px;">لا يوجد مشتركون مؤهلون لهذه القرعة في الفئة المحددة حالياً.</td></tr>';
                return;
            }

            tbody.innerHTML = items.map((c, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td><strong>${c.number}</strong></td>
                    <td>${c.name}</td>
                    <td><span class="role-badge staff" style="font-size: 0.75rem; padding: 2px 6px;">${c.category}</span></td>
                    <td>${c.phone || '-'}</td>
                    <td>الدورة ${c.cycle || 1}</td>
                    <td><strong class="text-green">${c.pay_ratio}%</strong></td>
                    <td><span class="badge-status" style="background: #dcfce7; color: #166534;">مؤهل ✅</span></td>
                </tr>
            `).join('');
        }

        function filterCandidatesTable(query) {
            if (!drawState.currentCandidates) return;
            const q = (query || '').trim().toLowerCase();
            if (!q) {
                renderCandidatesTable(drawState.currentCandidates);
                return;
            }
            const filtered = drawState.currentCandidates.filter(c =>
                (c.name && c.name.toLowerCase().includes(q)) ||
                (c.number && c.number.toLowerCase().includes(q)) ||
                (c.phone && c.phone.includes(q)) ||
                (c.category && c.category.toLowerCase().includes(q))
            );
            renderCandidatesTable(filtered);
        }

        function onCategoryFilterChange() {
            const sel = document.getElementById('draw_category_filter');
            if (sel) {
                drawState.selectedCategory = sel.value;
                loadAllDrawStats(false);
            }
        }

        // 2. --- Perform Draw & Animation Engine ---
        async function initiateDraw(drawType) {
            drawState.selectedDrawType = drawType;
            const cat = drawState.selectedCategory;
            const catParam = cat === 'الكل' ? '' : `&category=${encodeURIComponent(cat)}`;

            // Ensure fresh candidates before asking confirmation
            try {
                const res = await fetch(`/api/v1/draw/candidates?draw_type=${encodeURIComponent(drawType)}${catParam}`);
                if (!res.ok) throw new Error("فشل جلب المؤهلين");
                drawState.currentCandidates = await res.json();
            } catch (err) {
                showDrawAlert("تعذر جلب قائمة المؤهلين للسحب.", "danger");
                return;
            }

            if (!drawState.currentCandidates || drawState.currentCandidates.length === 0) {
                showDrawAlert(`لا يوجد أي مشتركين مؤهلين ومستوفين لشروط '${drawType}' حالياً لإجراء السحب!`, 'danger');
                return;
            }

            // If Grand Prize, check if multiple periods configured
            if (drawType === 'الجائزة الكبرى') {
                const periodsCount = parseInt(drawState.settings.grand_prize_periods_count || '1', 10);
                const weeksCount = parseInt(drawState.settings.grand_prize_weeks_per_period || '12', 10);

                if (periodsCount > 1) {
                    openGrandPeriodModal(periodsCount, weeksCount);
                    return;
                }
            }

            if (!confirm(`هل أنت متأكد من بدء '${drawType}' الآن؟\nعدد المؤهلين: ${drawState.currentCandidates.length} مشترك.`)) {
                return;
            }

            startDrawAnimation(drawType, 1);
        }

        function openGrandPeriodModal(periodsCount, weeksCount) {
            const modal = document.getElementById('grand-period-modal');
            const select = document.getElementById('grand-period-select');
            const desc = document.getElementById('grand-period-modal-desc');

            desc.textContent = `تم إعداد الجائزة الكبرى على ${periodsCount} فترات (${weeksCount} أسابيع لكل فترة). يرجى تحديد الفترة المراد إجراء السحب لها:`;
            select.innerHTML = '';
            for (let i = 1; i <= periodsCount; i++) {
                const wStart = (i - 1) * weeksCount + 1;
                const wEnd = i * weeksCount;
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = `الفترة ${i} (الأسابيع ${wStart} إلى ${wEnd})`;
                select.appendChild(opt);
            }

            modal.style.display = 'flex';
        }

        function closeGrandPeriodModal() {
            document.getElementById('grand-period-modal').style.display = 'none';
        }

        function proceedGrandDrawWithPeriod() {
            const select = document.getElementById('grand-period-select');
            const period = parseInt(select.value, 10) || 1;
            closeGrandPeriodModal();
            startDrawAnimation('الجائزة الكبرى', period);
        }

        async function startDrawAnimation(drawType, period = 1) {
            const overlay = document.getElementById('draw-modal-overlay');
            const modalTitle = document.getElementById('draw-modal-title');
            const rollerNum = document.getElementById('roller-number');
            const rollerName = document.getElementById('roller-name');
            const rollerCat = document.getElementById('roller-cat');
            const statusText = document.getElementById('roller-status-text');
            const resultCard = document.getElementById('winner-result-card');
            const modalFooter = document.getElementById('draw-modal-footer');
            const closeBtn = document.getElementById('btn-close-draw-modal');

            overlay.style.display = 'flex';
            modalTitle.textContent = `🎲 جاري السحب على: ${drawType}`;
            statusText.textContent = 'يتم الآن تدوير المشتركين المؤهلين عشوائياً لاختيار الفائز...';
            statusText.style.color = '#94a3b8';
            resultCard.style.display = 'none';
            resultCard.innerHTML = '';
            modalFooter.style.display = 'none';
            closeBtn.style.display = 'none';

            // Start Fast Slot Machine Shuffling
            let animCount = 0;
            const interval = setInterval(() => {
                const randomCand = drawState.currentCandidates[Math.floor(Math.random() * drawState.currentCandidates.length)];
                if (randomCand) {
                    rollerNum.textContent = randomCand.number;
                    rollerName.textContent = randomCand.name;
                    rollerCat.textContent = `الفئة: ${randomCand.category}`;
                }
                animCount++;
            }, 80);

            try {
                const selectedCat = drawState.selectedCategory === 'الكل' ? null : drawState.selectedCategory;
                const res = await fetch('/api/v1/draw/perform', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        draw_type: drawType,
                        category: selectedCat,
                        period: period
                    })
                });

                const data = await res.json();
                clearInterval(interval);

                if (!res.ok) {
                    overlay.style.display = 'none';
                    showDrawAlert(data.detail || 'تعذر إجراء السحب', 'danger');
                    return;
                }

                const winners = data.winners || [];
                if (winners.length > 0) {
                    const firstW = winners[0];
                    drawState.lastPerformedWinner = firstW;

                    rollerNum.textContent = firstW.subscriber_number;
                    rollerName.textContent = firstW.subscriber_name;
                    rollerCat.textContent = `الفئة: ${firstW.category}`;
                    statusText.textContent = '🎉 مبروك! تم اختيار الفائز وحفظ النتيجة بقاعدة البيانات.';
                    statusText.style.color = '#4ade80';

                    // Confetti Fanfare
                    triggerConfetti();

                    // Render Celebration Card inside Modal
                    resultCard.innerHTML = `
                        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid #10b981; border-radius: 12px; padding: 14px; text-align: right; margin-top: 10px;">
                            <div style="color: #facc15; font-size: 1.05rem; font-weight: 800; margin-bottom: 8px; text-align: center;">
                                🏆 بطاقة الفائز الرسمية
                            </div>
                            ${winners.map(w => `
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.84rem; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 6px; margin-bottom: 6px;">
                                    <div><span style="color: #94a3b8;">اسم الفائز:</span> <strong>${w.subscriber_name}</strong></div>
                                    <div><span style="color: #94a3b8;">رقم الحساب:</span> <strong>${w.subscriber_number}</strong></div>
                                    <div><span style="color: #94a3b8;">الفئة المالية:</span> <span>${w.category}</span></div>
                                    <div><span style="color: #94a3b8;">نوع السحب:</span> <span style="color: #facc15;">${w.draw_name}</span></div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                    resultCard.style.display = 'block';
                    modalFooter.style.display = 'flex';
                    closeBtn.style.display = 'block';

                    // Update main screen counts & statistics
                    loadAllDrawStats(false);
                }
            } catch (err) {
                clearInterval(interval);
                overlay.style.display = 'none';
                showDrawAlert("حدث خطأ في الاتصال أثناء إجراء السحب.", "danger");
            }
        }

        function closeDrawModal() {
            document.getElementById('draw-modal-overlay').style.display = 'none';
        }

        function printWinnerCertificate() {
            if (!drawState.lastPerformedWinner) return;
            const w = drawState.lastPerformedWinner;
            const printWin = window.open('', '', 'width=750,height=550');
            printWin.document.write(`
                <html lang="ar" dir="rtl">
                <head>
                    <title>إشعار فوز - ${w.subscriber_name}</title>
                    <style>
                        body { font-family: 'Tajawal', sans-serif; text-align: center; padding: 40px; background: #fff; color: #1e293b; }
                        .cert { border: 4px double #d97706; border-radius: 16px; padding: 30px; max-width: 600px; margin: 0 auto; }
                        h1 { color: #166534; font-size: 26px; margin-bottom: 10px; }
                        h2 { color: #d97706; font-size: 20px; margin-top: 0; }
                        .info { font-size: 16px; margin: 20px 0; line-height: 1.8; text-align: right; }
                        .footer { margin-top: 30px; display: flex; justify-content: space-between; font-size: 14px; }
                    </style>
                </head>
                <body>
                    <div class="cert">
                        <h1>🏆 إشعار الفوز بالقرعة 🏆</h1>
                        <h2>هكبة المليون الاستثمارية</h2>
                        <div class="info">
                            <p>تشهد إدارة المنصة بأن المشترك: <strong>${w.subscriber_name}</strong></p>
                            <p>رقم الحساب: <strong>${w.subscriber_number}</strong> | الفئة: <strong>${w.category}</strong></p>
                            <p>قد فاز بـ: <strong>${w.draw_name}</strong></p>
                            <p>بتاريخ: <strong>${w.draw_date || new Date().toLocaleDateString('ar-SA')}</strong></p>
                        </div>
                        <div class="footer">
                            <div>الختم الرسمي: ....................</div>
                            <div>توقيع الإدارة: ....................</div>
                        </div>
                    </div>
                    <script>window.print();<\/script>
                </body>
                </html>
            `);
            printWin.document.close();
        }

        // 3. --- Winners Log Tab ---
        async function loadWinnersTab() {
            const tbody = document.getElementById('winners-tbody');
            if (!tbody) return;

            const drawType = document.getElementById('filter-winner-draw-type')?.value || 'الكل';
            const cat = document.getElementById('filter-winner-cat')?.value || 'الكل';
            const search = document.getElementById('filter-winner-search')?.value || '';

            const params = new URLSearchParams();
            if (drawType !== 'الكل') params.append('draw_type', drawType);
            if (cat !== 'الكل') params.append('category', cat);
            if (search.trim()) params.append('search', search.trim());
            params.append('limit', '100');

            try {
                const res = await fetch(`/api/v1/draw/winners?${params.toString()}`);
                if (res.ok) {
                    drawState.currentWinners = await res.json();
                } else {
                    drawState.currentWinners = [];
                }
                renderWinnersTable(drawState.currentWinners);
            } catch (e) {
                console.error("Load winners error:", e);
                tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #ef4444; padding: 18px;">حدث خطأ أثناء تحميل سجل الفائزين.</td></tr>';
            }
        }

        function renderWinnersTable(items) {
            const tbody = document.getElementById('winners-tbody');
            if (!tbody) return;

            if (!items || items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #94a3b8; padding: 18px;">لا يوجد فائزون مطابقون لخيارات التصفية الحالية.</td></tr>';
                return;
            }

            tbody.innerHTML = items.map((w, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td><strong>${w.subscriber_name}</strong></td>
                    <td>${w.subscriber_number}</td>
                    <td><span class="role-badge staff" style="font-size: 0.75rem; padding: 2px 6px;">${w.category || '-'}</span></td>
                    <td>${w.phone || '-'}</td>
                    <td>الدورة ${w.cycle_number || 1}</td>
                    <td><strong style="color: #b45309;">🏆 ${w.draw_name}</strong></td>
                    <td>${w.draw_date || '-'}</td>
                    <td>
                        <button type="button" class="badge-status" style="border: none; cursor: pointer; ${w.is_received ? 'background: #dcfce7; color: #166534;' : 'background: #fef3c7; color: #b45309;'}" onclick="toggleWinnerReceipt(${w.id}, ${w.is_received})">
                            ${w.is_received ? 'مستلم ✅' : 'قيد الانتظار ⏳'}
                        </button>
                    </td>
                    <td>
                        <button type="button" class="btn-compact btn-danger" style="height: 26px; padding: 2px 8px; font-size: 0.75rem;" onclick="deleteWinnerRecord(${w.id})" title="حذف الفائز">
                            🗑️
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        function debounceWinnersSearch() {
            clearTimeout(drawState.winnersSearchTimer);
            drawState.winnersSearchTimer = setTimeout(() => {
                loadWinnersTab();
            }, 300);
        }

        async function toggleWinnerReceipt(winnerId, currentStatus) {
            try {
                const res = await fetch(`/api/v1/draw/winners/${winnerId}/receipt`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ is_received: !currentStatus })
                });
                if (res.ok) {
                    loadWinnersTab();
                } else {
                    showDrawAlert("تعذر تحديث حالة استلام الفائز.", "danger");
                }
            } catch (e) {
                showDrawAlert("خطأ في الاتصال بالخادم.", "danger");
            }
        }

        async function deleteWinnerRecord(winnerId) {
            if (!confirm("هل أنت متأكد من حذف سجل الفائز هذا من قاعدة البيانات؟ لا يمكن التراجع عن هذا الإجراء.")) {
                return;
            }
            try {
                const res = await fetch(`/api/v1/draw/winners/${winnerId}`, {
                    method: 'DELETE'
                });
                if (res.ok) {
                    showDrawAlert("تم حذف سجل الفائز بنجاح.", "success");
                    loadWinnersTab();
                    loadAllDrawStats(false);
                } else {
                    showDrawAlert("تعذر حذف سجل الفائز.", "danger");
                }
            } catch (e) {
                showDrawAlert("خطأ في الاتصال أثناء الحذف.", "danger");
            }
        }

        function exportWinnersCSV() {
            if (!drawState.currentWinners || drawState.currentWinners.length === 0) {
                showDrawAlert("لا توجد بيانات فائزين للتصدير.", "info");
                return;
            }
            const headers = ["م", "اسم المشترك", "رقم الحساب", "الفئة المالية", "رقم الهاتف", "رقم الدورة", "نوع الجائزة", "تاريخ السحب", "حالة الاستلام"];
            const rows = drawState.currentWinners.map((w, idx) => [
                idx + 1,
                `"${(w.subscriber_name || '').replace(/"/g, '""')}"`,
                `"${w.subscriber_number || ''}"`,
                `"${w.category || ''}"`,
                `"${w.phone || ''}"`,
                w.cycle_number || 1,
                `"${(w.draw_name || '').replace(/"/g, '""')}"`,
                `"${w.draw_date || ''}"`,
                w.is_received ? "مستلم" : "قيد الانتظار"
            ]);
            downloadCSV("سجل_الفائزين_هكبة_المليون.csv", headers, rows);
        }

        // 4. --- Excluded Members Tab ---
        async function loadExcludedTab() {
            const tbody = document.getElementById('excluded-tbody');
            if (!tbody) return;

            const cat = document.getElementById('filter-excluded-cat')?.value || 'الكل';
            const search = document.getElementById('filter-excluded-search')?.value || '';

            const params = new URLSearchParams();
            if (cat !== 'الكل') params.append('category', cat);
            if (search.trim()) params.append('search', search.trim());

            try {
                const res = await fetch(`/api/v1/draw/excluded?${params.toString()}`);
                if (res.ok) {
                    drawState.currentExcluded = await res.json();
                } else {
                    drawState.currentExcluded = [];
                }
                renderExcludedTable(drawState.currentExcluded);
            } catch (e) {
                console.error("Load excluded error:", e);
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #ef4444; padding: 18px;">حدث خطأ أثناء تحميل قائمة المستبعدين.</td></tr>';
            }
        }

        function renderExcludedTable(items) {
            const tbody = document.getElementById('excluded-tbody');
            if (!tbody) return;

            if (!items || items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 18px;">لا يوجد مستبعدون مطابقون لخيارات التصفية.</td></tr>';
                return;
            }

            tbody.innerHTML = items.map((e, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td><strong>${e.name}</strong></td>
                    <td>${e.subscriber_number}</td>
                    <td><span class="role-badge staff" style="font-size: 0.75rem; padding: 2px 6px;">${e.category}</span></td>
                    <td>${e.phone || '-'}</td>
                    <td style="color: #b91c1c; font-weight: 600;">${e.reason}</td>
                    <td><span class="badge-status" style="background: #fee2e2; color: #991b1b;">${e.status_badge || 'مستبعد'}</span></td>
                </tr>
            `).join('');
        }

        function debounceExcludedSearch() {
            clearTimeout(drawState.excludedSearchTimer);
            drawState.excludedSearchTimer = setTimeout(() => {
                loadExcludedTab();
            }, 300);
        }

        function exportExcludedCSV() {
            if (!drawState.currentExcluded || drawState.currentExcluded.length === 0) {
                showDrawAlert("لا توجد بيانات مستبعدين للتصدير.", "info");
                return;
            }
            const headers = ["م", "اسم المشترك", "رقم الحساب", "الفئة المالية", "رقم الهاتف", "سبب الاستبعاد", "الحالة"];
            const rows = drawState.currentExcluded.map((e, idx) => [
                idx + 1,
                `"${(e.name || '').replace(/"/g, '""')}"`,
                `"${e.subscriber_number || ''}"`,
                `"${e.category || ''}"`,
                `"${e.phone || ''}"`,
                `"${(e.reason || '').replace(/"/g, '""')}"`,
                `"${e.status_badge || ''}"`
            ]);
            downloadCSV("المستبعدين_من_السحب.csv", headers, rows);
        }

        // 5. --- Draw Settings Tab ---
        async function loadDrawSettingsTab() {
            try {
                const res = await fetch('/api/v1/draw/settings');
                if (res.ok) {
                    drawState.settings = await res.json();
                } else {
                    drawState.settings = {};
                }

                // Checkboxes
                document.getElementById('chk_late_1').checked = drawState.settings.incentive_allow_late_1 === '1';
                document.getElementById('chk_late_2').checked = drawState.settings.incentive_allow_late_2 === '1';
                document.getElementById('chk_late_3').checked = drawState.settings.incentive_allow_late_3 === '1';

                // Grand Prize
                document.getElementById('spin_grand_periods').value = parseInt(drawState.settings.grand_prize_periods_count || '1', 10);
                document.getElementById('spin_grand_weeks').value = parseInt(drawState.settings.grand_prize_weeks_per_period || '12', 10);
                document.getElementById('spin_grand_winners').value = parseInt(drawState.settings.grand_prize_winners_count || '1', 10);

                if (drawState.settings.grand_prize_start_date) {
                    document.getElementById('dt_grand_start').value = drawState.settings.grand_prize_start_date;
                }
                if (drawState.settings.grand_prize_end_date) {
                    document.getElementById('dt_grand_end').value = drawState.settings.grand_prize_end_date;
                }

                updateGrandPeriodSummary();
            } catch (e) {
                console.error("Load draw settings error:", e);
            }
        }

        function updateGrandPeriodSummary() {
            const periods = parseInt(document.getElementById('spin_grand_periods').value || '1', 10);
            const weeks = parseInt(document.getElementById('spin_grand_weeks').value || '12', 10);
            const total = periods * weeks;
            const banner = document.getElementById('grand-calc-summary');
            if (banner) {
                banner.textContent = `👑 نظام فترات الجائزة الكبرى: تم ضبط ${periods} فترات، وكل فترة مدتها ${weeks} أسابيع (إجمالي مدة الدورة: ${total} أسبوعاً). يتم السحب بنهاية كل فترة للمستوفين.`;
            }
        }

        async function saveIncentiveSettings() {
            const payload = {
                incentive_allow_late_1: document.getElementById('chk_late_1').checked ? '1' : '0',
                incentive_allow_late_2: document.getElementById('chk_late_2').checked ? '1' : '0',
                incentive_allow_late_3: document.getElementById('chk_late_3').checked ? '1' : '0'
            };
            try {
                const res = await fetch('/api/v1/draw/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    showDrawAlert("تم حفظ إعدادات الجائزة التحفيزية بنجاح.", "success");
                    loadAllDrawStats(false);
                } else {
                    showDrawAlert("تعذر حفظ إعدادات التحفيزية.", "danger");
                }
            } catch (e) {
                showDrawAlert("خطأ في الاتصال بالخادم أثناء الحفظ.", "danger");
            }
        }

        async function saveGrandPrizeSettings() {
            const payload = {
                grand_prize_periods_count: String(document.getElementById('spin_grand_periods').value || '1'),
                grand_prize_weeks_per_period: String(document.getElementById('spin_grand_weeks').value || '12'),
                grand_prize_winners_count: String(document.getElementById('spin_grand_winners').value || '1'),
                grand_prize_start_date: document.getElementById('dt_grand_start').value,
                grand_prize_end_date: document.getElementById('dt_grand_end').value
            };
            try {
                const res = await fetch('/api/v1/draw/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    showDrawAlert("تم حفظ إعدادات الجائزة الكبرى بنجاح.", "success");
                    loadAllDrawStats(false);
                } else {
                    showDrawAlert("تعذر حفظ إعدادات الجائزة الكبرى.", "danger");
                }
            } catch (e) {
                showDrawAlert("خطأ في الاتصال بالخادم أثناء الحفظ.", "danger");
            }
        }

        // CSV Downloader with UTF-8 BOM
        function downloadCSV(filename, headers, rows) {
            const csvContent = "\uFEFF" + [headers.join(",")].concat(rows.map(r => r.join(","))).join("\n");
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        // Confetti Fireworks Animation
        function triggerConfetti() {
            const canvas = document.getElementById('confetti-canvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;

            const pieces = [];
            const colors = ['#f59e0b', '#10b981', '#3b82f6', '#ec4899', '#facc15', '#ffffff'];
            for (let i = 0; i < 150; i++) {
                pieces.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height - canvas.height,
                    size: Math.random() * 8 + 4,
                    color: colors[Math.floor(Math.random() * colors.length)],
                    speed: Math.random() * 4 + 2,
                    angle: Math.random() * 360,
                    spin: Math.random() * 0.2 - 0.1
                });
            }

            let animationFrame;
            let start = Date.now();
            function draw() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                pieces.forEach(p => {
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate(p.angle);
                    ctx.fillStyle = p.color;
                    ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
                    ctx.restore();

                    p.y += p.speed;
                    p.angle += p.spin;
                    if (p.y > canvas.height) p.y = -10;
                });

                if (Date.now() - start < 4500) {
                    animationFrame = requestAnimationFrame(draw);
                } else {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    cancelAnimationFrame(animationFrame);
                }
            }
            draw();
        }

        // ==============================================
        // --- Cycles & Installments Logic (Manager Only) ---
        // ==============================================
        let categoriesCyclesData = [];
        try {
            categoriesCyclesData = JSON.parse('{{ categories_json | safe }}');
        } catch (e) {
            categoriesCyclesData = [];
        }

        function showCyclesAlert(message, type = 'info') {
            const box = document.getElementById('cycles-alert');
            if (!box) return;
            box.textContent = message;
            box.className = 'alert ' + (type === 'success' ? 'alert-success' : type === 'info' ? 'alert-info' : 'alert-danger');
            box.style.display = 'block';
            box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            setTimeout(() => {
                if (box) box.style.display = 'none';
            }, 6000);
        }

        function onCyclesTabOpened() {
            const cycSel = document.getElementById('cyc_cat');
            if (cycSel && !cycSel.value && cycSel.options.length > 1) {
                cycSel.selectedIndex = 1;
                loadCategoryCycleSettings();
            }
        }

        function loadCategoryCycleSettings() {
            const catId = Number(document.getElementById('cyc_cat').value);
            if (!catId) return;

            const cat = categoriesCyclesData.find(c => c.id === catId);
            if (!cat) return;

            document.getElementById('cyc_count').value = cat.max_cycles || 1;
            document.getElementById('cyc_inst_count').value = cat.max_installments || 12;

            if (cat.start_date) {
                document.getElementById('cyc_start').value = cat.start_date;
            } else {
                const today = new Date().toISOString().split('T')[0];
                document.getElementById('cyc_start').value = today;
            }

            if (cat.end_date) {
                document.getElementById('cyc_end').value = cat.end_date;
            }

            updateAutoEndDate();
        }

        function updateAutoEndDate() {
            const countInput = document.getElementById('cyc_count');
            const instInput = document.getElementById('cyc_inst_count');
            const startInput = document.getElementById('cyc_start');
            const endInput = document.getElementById('cyc_end');

            const previewTotal = document.getElementById('cyc-preview-total');
            const previewDays = document.getElementById('cyc-preview-days');

            const cycles = parseInt(countInput.value) || 0;
            const inst = parseInt(instInput.value) || 0;
            const totalInst = cycles * inst;

            if (previewTotal) previewTotal.textContent = `${totalInst} قسط`;
            if (previewDays) previewDays.textContent = `${totalInst} يوماً`;

            if (!startInput.value || totalInst <= 0) return;

            try {
                const start = new Date(startInput.value);
                if (isNaN(start.getTime())) return;

                // Daily Hakbah logic: 1 day per installment -> (totalInst - 1) days added
                const days = Math.max(0, totalInst - 1);
                const end = new Date(start.getTime() + days * 24 * 60 * 60 * 1000);
                endInput.value = end.toISOString().split('T')[0];
            } catch (e) {
                console.error("Auto end date error:", e);
            }
        }

        async function saveCycleSettings() {
            const catId = Number(document.getElementById('cyc_cat').value);
            if (!catId) {
                showCyclesAlert('يرجى اختيار الفئة أولاً', 'danger');
                return;
            }

            const cycles = parseInt(document.getElementById('cyc_count').value);
            const inst = parseInt(document.getElementById('cyc_inst_count').value);
            const startDate = document.getElementById('cyc_start').value;
            const endDate = document.getElementById('cyc_end').value;

            if (!cycles || cycles < 1 || !inst || inst < 1) {
                showCyclesAlert('يرجى إدخال أرقام صحيحة لعدد الدورات والأقساط (1 على الأقل)', 'danger');
                return;
            }

            const btn = document.getElementById('btn-save-cycle');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span>⏳</span> جاري الحفظ...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/cycles/save-settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category_id: catId,
                        max_cycles: cycles,
                        max_installments: inst,
                        start_date: startDate,
                        end_date: endDate
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    showCyclesAlert(data.message, 'success');
                    const idx = categoriesCyclesData.findIndex(c => c.id === catId);
                    if (idx !== -1) {
                        categoriesCyclesData[idx].max_cycles = cycles;
                        categoriesCyclesData[idx].max_installments = inst;
                        categoriesCyclesData[idx].start_date = startDate;
                        categoriesCyclesData[idx].end_date = endDate;
                    }
                } else {
                    showCyclesAlert(data.message || 'فشل حفظ الإعدادات', 'danger');
                }
            } catch (err) {
                showCyclesAlert('حدث خطأ في الاتصال بالخادم', 'danger');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        async function generateCycleSchedule() {
            const catId = Number(document.getElementById('cyc_cat').value);
            if (!catId) {
                showCyclesAlert('يرجى اختيار الفئة أولاً', 'danger');
                return;
            }

            const cycles = parseInt(document.getElementById('cyc_count').value);
            const inst = parseInt(document.getElementById('cyc_inst_count').value);
            const startDate = document.getElementById('cyc_start').value;

            if (!cycles || cycles < 1 || !inst || inst < 1) {
                showCyclesAlert('يرجى إدخال أرقام صحيحة لعدد الدورات والأقساط', 'danger');
                return;
            }

            const totalInst = cycles * inst;
            const catSelect = document.getElementById('cyc_cat');
            const catName = catSelect.options[catSelect.selectedIndex].text;

            const confirmMsg = `سيتم إنشاء ${totalInst} سجل دفع (بمعدل قسط واحد يومياً) لكل مشترك في:\n${catName}\n\nهل أنت متأكد من المتابعة وتوليد الأقساط؟`;
            if (!confirm(confirmMsg)) {
                return;
            }

            const btn = document.getElementById('btn-gen-cycle');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<span>⚡</span> جاري توليد جدول الأقساط...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/cycles/generate-schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category_id: catId,
                        max_cycles: cycles,
                        max_installments: inst,
                        start_date: startDate
                    })
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    showCyclesAlert(data.message, 'success');
                    const idx = categoriesCyclesData.findIndex(c => c.id === catId);
                    if (idx !== -1) {
                        categoriesCyclesData[idx].max_cycles = cycles;
                        categoriesCyclesData[idx].max_installments = inst;
                        categoriesCyclesData[idx].start_date = startDate;
                    }
                } else {
                    showCyclesAlert(data.message || 'فشل توليد جدول الأقساط', 'danger');
                }
            } catch (err) {
                showCyclesAlert('حدث خطأ في الاتصال بالخادم', 'danger');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        // Initialize Draw data when Manager views draw tab
        document.addEventListener('DOMContentLoaded', () => {
            loadAllDrawStats(false);
            loadDrawSettingsTab();
        });

        // =========================================================================
        // Messaging & Awareness Management JavaScript
        // =========================================================================
        let allMsgData = [];
        let editingMsgId = null;

        async function loadMessagesTab() {
            try {
                const res = await fetch('/api/admin/messages');
                if (!res.ok) {
                    showMsgAlert('فشل تحميل الرسائل. تأكد من صلاحيات المدير.', 'danger');
                    return;
                }
                const data = await res.json();
                allMsgData = data.messages || [];

                // Update stats
                document.getElementById('msg-stat-total').textContent = data.stats.total;
                document.getElementById('msg-stat-active').textContent = data.stats.active;
                document.getElementById('msg-stat-expired').textContent = data.stats.expired;

                applyMsgFilters();
            } catch(e) {
                showMsgAlert('خطأ في الاتصال بالخادم', 'danger');
            }
        }

        function applyMsgFilters() {
            const typeFilter = document.getElementById('msg-filter-type').value;
            const statusFilter = document.getElementById('msg-filter-status').value;

            let filtered = allMsgData.filter(m => {
                const typeMatch = (typeFilter === 'all') || (m.msg_type === typeFilter);
                let statusMatch = true;
                if (statusFilter === 'active') statusMatch = m.is_effectively_active;
                else if (statusFilter === 'inactive') statusMatch = !m.is_active;
                else if (statusFilter === 'expired') statusMatch = m.is_expired;
                return typeMatch && statusMatch;
            });

            renderMsgTable(filtered);
        }

        const MSG_TYPE_MAP = {
            awareness:   { label: '💡 توعوية',      color: '#10b981', bg: '#d1fae5' },
            educational: { label: '📚 تعليمية',      color: '#3b82f6', bg: '#dbeafe' },
            reminder:    { label: '⏰ تذكيرية',      color: '#f59e0b', bg: '#fef3c7' },
            urgent:      { label: '⚠️ تنبيه هام',   color: '#ef4444', bg: '#fee2e2' },
            general:     { label: '📢 إعلان عام',    color: '#8b5cf6', bg: '#ede9fe' }
        };

        function renderMsgTable(messages) {
            const tbody = document.getElementById('msg-table-body');
            const emptyState = document.getElementById('msg-empty-state');

            if (!messages || messages.length === 0) {
                tbody.innerHTML = '';
                emptyState.style.display = 'block';
                return;
            }
            emptyState.style.display = 'none';

            tbody.innerHTML = messages.map((m, idx) => {
                const typeInfo = MSG_TYPE_MAP[m.msg_type] || { label: m.msg_type, color: '#64748b', bg: '#f1f5f9' };
                const contentPreview = (m.content || '').length > 55 ? m.content.substring(0, 52) + '...' : m.content;
                const endDateStr = m.end_date
                    ? `<span style="color: ${m.is_expired ? '#ef4444' : '#64748b'};">${m.is_expired ? '⌛ ' : ''}${m.end_date.replace('T', ' ')}</span>`
                    : '<span style="color: #94a3b8;">♾️ دائمة</span>';

                let statusBadge;
                if (!m.is_active) {
                    statusBadge = '<span class="badge-status" style="background: #f1f5f9; color: #64748b;">⚪ معطلة</span>';
                } else if (m.is_expired) {
                    statusBadge = '<span class="badge-status" style="background: #fee2e2; color: #991b1b;">⌛ منتهية</span>';
                } else {
                    statusBadge = '<span class="badge-status" style="background: #d1fae5; color: #065f46;">🟢 نشطة</span>';
                }

                return `<tr>
                    <td style="text-align:center; color:#64748b;">${idx + 1}</td>
                    <td style="text-align:center;">
                        <span style="background:${typeInfo.bg}; color:${typeInfo.color}; padding:2px 7px; border-radius:6px; font-size:0.78rem; font-weight:700;">${typeInfo.label}</span>
                    </td>
                    <td style="font-weight:700; color:#0f172a;" title="${m.title}">${m.title}</td>
                    <td style="color:#475569;" title="${m.content}">${contentPreview}</td>
                    <td style="text-align:center; color:#64748b;">${m.display_duration} ث</td>
                    <td style="text-align:center; color:#64748b;">${m.priority}</td>
                    <td style="text-align:center; font-size:0.78rem;">${endDateStr}</td>
                    <td style="text-align:center;">${statusBadge}</td>
                    <td style="text-align:center;">
                        <div style="display:flex; gap:5px; justify-content:center;">
                            <button onclick="toggleMsg(${m.id})"
                                style="background:${m.is_active ? '#fef3c7' : '#d1fae5'}; color:${m.is_active ? '#b45309' : '#065f46'}; border:none; padding:3px 8px; border-radius:5px; font-size:0.75rem; cursor:pointer; font-family:inherit;">
                                ${m.is_active ? 'تعطيل' : 'تفعيل'}
                            </button>
                            <button onclick="editMsg(${m.id})"
                                style="background:#dbeafe; color:#1e40af; border:none; padding:3px 8px; border-radius:5px; font-size:0.75rem; cursor:pointer; font-family:inherit;">
                                تعديل
                            </button>
                            <button onclick="deleteMsg(${m.id}, '${m.title.replace(/'/g, "\\'")}')"
                                style="background:#fee2e2; color:#991b1b; border:none; padding:3px 8px; border-radius:5px; font-size:0.75rem; cursor:pointer; font-family:inherit;">
                                حذف
                            </button>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        }

        function showMsgAlert(text, type = 'info') {
            const box = document.getElementById('msg-alert-box');
            box.className = `alert alert-${type}`;
            box.textContent = text;
            box.style.display = 'flex';
            setTimeout(() => { box.style.display = 'none'; }, 4000);
        }

        // --- Modal Management ---
        function openMessageModal(msgData = null) {
            editingMsgId = msgData ? msgData.id : null;
            const modal = document.getElementById('msg-modal');
            const title = document.getElementById('msg-modal-title');

            if (msgData) {
                title.textContent = '✏️ تعديل الرسالة';
                document.getElementById('msg-in-title').value = msgData.title || '';
                document.getElementById('msg-in-content').value = msgData.content || '';
                document.getElementById('msg-in-type').value = msgData.msg_type || 'awareness';
                document.getElementById('msg-in-category').value = msgData.target_category || 'all';
                document.getElementById('msg-in-duration').value = msgData.display_duration || 7;
                document.getElementById('msg-in-priority').value = msgData.priority || 1;
                document.getElementById('msg-in-active').checked = msgData.is_active !== false;

                const hasExpiry = !!msgData.end_date;
                document.getElementById('msg-has-expiry').checked = hasExpiry;
                document.getElementById('msg-expiry-inputs').style.display = hasExpiry ? 'block' : 'none';
                if (hasExpiry && msgData.end_date) {
                    document.getElementById('msg-in-enddate').value = msgData.end_date;
                }
            } else {
                title.textContent = '➕ إضافة رسالة جديدة';
                document.getElementById('msg-in-title').value = '';
                document.getElementById('msg-in-content').value = '';
                document.getElementById('msg-in-type').value = 'awareness';
                document.getElementById('msg-in-category').value = 'all';
                document.getElementById('msg-in-duration').value = 7;
                document.getElementById('msg-in-priority').value = 1;
                document.getElementById('msg-in-active').checked = true;
                document.getElementById('msg-has-expiry').checked = false;
                document.getElementById('msg-expiry-inputs').style.display = 'none';
                document.getElementById('msg-in-enddate').value = '';
            }

            modal.style.display = 'flex';
        }

        function closeMsgModal() {
            document.getElementById('msg-modal').style.display = 'none';
            editingMsgId = null;
        }

        function toggleMsgExpiry(checked) {
            document.getElementById('msg-expiry-inputs').style.display = checked ? 'block' : 'none';
        }

        function setMsgExpiry(days) {
            const dt = new Date();
            dt.setDate(dt.getDate() + days);
            const pad = n => String(n).padStart(2, '0');
            const val = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
            document.getElementById('msg-in-enddate').value = val;
        }

        async function saveMsgForm() {
            const title = document.getElementById('msg-in-title').value.trim();
            const content = document.getElementById('msg-in-content').value.trim();

            if (!title) { showMsgAlert('يرجى كتابة عنوان الرسالة', 'danger'); return; }
            if (!content) { showMsgAlert('يرجى كتابة نص ومحتوى الرسالة', 'danger'); return; }

            const hasExpiry = document.getElementById('msg-has-expiry').checked;
            let end_date = null;
            if (hasExpiry) {
                end_date = document.getElementById('msg-in-enddate').value || null;
                if (end_date && new Date(end_date) <= new Date()) {
                    showMsgAlert('تاريخ الانتهاء يجب أن يكون في المستقبل', 'danger');
                    return;
                }
            }

            const payload = {
                title,
                content,
                msg_type: document.getElementById('msg-in-type').value,
                target_category: document.getElementById('msg-in-category').value,
                display_duration: parseInt(document.getElementById('msg-in-duration').value) || 7,
                priority: parseInt(document.getElementById('msg-in-priority').value) || 1,
                is_active: document.getElementById('msg-in-active').checked,
                end_date
            };

            const saveBtn = document.getElementById('msg-modal-save-btn');
            saveBtn.disabled = true;
            saveBtn.textContent = 'جاري الحفظ...';

            try {
                const url = editingMsgId ? `/api/admin/messages/${editingMsgId}` : '/api/admin/messages';
                const method = editingMsgId ? 'PUT' : 'POST';
                const res = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    closeMsgModal();
                    showMsgAlert(data.message || 'تم الحفظ بنجاح ✅', 'success');
                    await loadMessagesTab();
                } else {
                    showMsgAlert(data.error || 'فشل حفظ الرسالة', 'danger');
                }
            } catch(e) {
                showMsgAlert('خطأ في الاتصال بالخادم', 'danger');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = '💾 حفظ الرسالة';
            }
        }

        function editMsg(id) {
            const msg = allMsgData.find(m => m.id === id);
            if (msg) openMessageModal(msg);
        }

        async function toggleMsg(id) {
            try {
                const res = await fetch(`/api/admin/messages/${id}/toggle`, { method: 'PATCH' });
                const data = await res.json();
                if (res.ok && data.success) {
                    showMsgAlert(data.message, 'success');
                    await loadMessagesTab();
                } else {
                    showMsgAlert(data.error || 'فشل تغيير حالة الرسالة', 'danger');
                }
            } catch(e) {
                showMsgAlert('خطأ في الاتصال', 'danger');
            }
        }

        async function deleteMsg(id, title) {
            if (!confirm(`هل أنت متأكد من حذف الرسالة:\n«${title}»\n\nهذا الإجراء لا يمكن التراجع عنه.`)) return;
            try {
                const res = await fetch(`/api/admin/messages/${id}`, { method: 'DELETE' });
                const data = await res.json();
                if (res.ok && data.success) {
                    showMsgAlert(data.message || 'تم حذف الرسالة بنجاح', 'success');
                    await loadMessagesTab();
                } else {
                    showMsgAlert(data.error || 'فشل حذف الرسالة', 'danger');
                }
            } catch(e) {
                showMsgAlert('خطأ في الاتصال', 'danger');
            }
        }

        // Close msg modal on overlay click
        document.getElementById('msg-modal').addEventListener('click', function(e) {
            if (e.target === this) closeMsgModal();
        });

        // --- Viewport Mode Toggle (Desktop View vs Mobile View) ---
        function toggleDesktopView() {
            const meta = document.getElementById('viewport-meta') || document.querySelector('meta[name="viewport"]');
            const isDesktop = localStorage.getItem('hakbah_desktop_mode') === 'true';
            const icon = document.getElementById('viewport-toggle-icon');
            const text = document.getElementById('viewport-toggle-text');

            if (!isDesktop) {
                // Switch to authentic Desktop view as seen on PC
                if (meta) meta.setAttribute('content', 'width=1280, initial-scale=0.32, minimum-scale=0.2, maximum-scale=3.0, user-scalable=yes');
                localStorage.setItem('hakbah_desktop_mode', 'true');
                if (icon) icon.textContent = '📱';
                if (text) text.textContent = 'عرض كالهاتف';
            } else {
                // Switch back to responsive Mobile view
                if (meta) meta.setAttribute('content', 'width=device-width, initial-scale=1.0');
                localStorage.setItem('hakbah_desktop_mode', 'false');
                if (icon) icon.textContent = '🖥️';
                if (text) text.textContent = 'عرض كالحاسوب';
            }
        }


        // ── Visitors Stats Functions ──
        function loadVisitorsStats() {
            fetch('/api/stats/visitors')
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (!data) return;
                    const onlineEl = document.getElementById('stat-online-count');
                    const visitsEl = document.getElementById('stat-total-visits');
                    const visitingEl = document.getElementById('stat-visiting-subs');
                    const todayEl = document.getElementById('stat-today-visits');
                    if (onlineEl) onlineEl.textContent = data.online_count ?? '—';
                    if (visitsEl) visitsEl.textContent = (data.total_subscriber_visits || 0) + (data.total_site_visits || 0);
                    if (visitingEl) visitingEl.textContent = data.visiting_subscribers_count ?? '—';
                    if (todayEl) todayEl.textContent = data.today_site_visits ?? '—';
                })
                .catch(() => {});
        }

        function loadOnlineSubscribers() {
            const modal = document.getElementById('online-subs-modal');
            if (!modal) return;
            modal.style.display = 'flex';
            const wrap = document.getElementById('online-subs-table-wrap');
            if (wrap) wrap.innerHTML = '<p style="text-align:center;color:#94a3b8;padding:30px 0;">جاري التحميل...</p>';

            fetch('/api/stats/visitors')
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (!data || !wrap) return;
                    const list = data.online_subscribers || [];
                    if (list.length === 0) {
                        wrap.innerHTML = '<div style="text-align:center;padding:50px 0;"><div style="font-size:3rem;margin-bottom:12px;">😴</div><p style="color:#94a3b8;font-size:1rem;">لا يوجد مشتركون متصلون في هذه اللحظة</p></div>';
                        return;
                    }
                    let html = '<table style="width:100%;border-collapse:collapse;font-size:0.9rem;text-align:right;">';
                    html += '<thead><tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">الاسم</th>';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">رقم الحساب</th>';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">رقم الهاتف</th>';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">الفئة</th>';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">آخر نشاط</th>';
                    html += '<th style="padding:10px 12px;font-weight:700;color:#475569;">الزيارات</th>';
                    html += '</tr></thead><tbody>';
                    list.forEach((s, i) => {
                        const bg = i % 2 === 0 ? '#fff' : '#f8fafc';
                        const timeStr = s.minutes_ago === 0 ? '<span style="color:#059669;font-weight:700;">الآن 🟢</span>' :
                            `<span style="color:#0284c7;">منذ ${s.minutes_ago} د</span>`;
                        html += `<tr style="background:${bg};border-bottom:1px solid #f1f5f9;">`;
                        html += `<td style="padding:10px 12px;font-weight:700;color:#1e293b;">🟢 ${s.name}</td>`;
                        html += `<td style="padding:10px 12px;color:#475569;">${s.subscriber_number || '—'}</td>`;
                        html += `<td style="padding:10px 12px;color:#475569;">${s.phone || '—'}</td>`;
                        html += `<td style="padding:10px 12px;color:#475569;">${s.category || '—'}</td>`;
                        html += `<td style="padding:10px 12px;">${timeStr}</td>`;
                        html += `<td style="padding:10px 12px;font-weight:700;color:#7c3aed;">${s.visit_count}</td>`;
                        html += '</tr>';
                    });
                    html += '</tbody></table>';
                    wrap.innerHTML = html;
                })
                .catch(() => {
                    if (wrap) wrap.innerHTML = '<p style="text-align:center;color:#ef4444;padding:30px 0;">تعذر تحميل البيانات</p>';
                });
        }

        // Load stats on page load, then every 30s
        document.addEventListener('DOMContentLoaded', function() {
            if (document.getElementById('stat-online-count')) {
                loadVisitorsStats();
                setInterval(loadVisitorsStats, 15000);
            }
        });

        // Close modal on outside click
        document.addEventListener('click', function(e) {
            const modal = document.getElementById('online-subs-modal');
            if (modal && e.target === modal) modal.style.display = 'none';
        });

        // Apply saved preference immediately on page load
        (function() {
            try {
                if (localStorage.getItem('hakbah_desktop_mode') === 'true') {
                    const meta = document.getElementById('viewport-meta') || document.querySelector('meta[name="viewport"]');
                    if (meta) meta.setAttribute('content', 'width=1280, initial-scale=0.32, minimum-scale=0.2, maximum-scale=3.0, user-scalable=yes');
                    document.addEventListener('DOMContentLoaded', function() {
                        const icon = document.getElementById('viewport-toggle-icon');
                        const text = document.getElementById('viewport-toggle-text');
                        if (icon) icon.textContent = '📱';
                        if (text) text.textContent = 'عرض كالهاتف';
                    });
                }
            } catch(e) {}
        })();