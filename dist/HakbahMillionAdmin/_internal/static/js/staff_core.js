/* staff_core.js - منطق التبويب والدفعات الأساسي - مستخرج تلقائياً */

// --- Tab Switching Logic ---
        function switchMainTab(tabId, btn) {
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
            if (tabId === 'my-payments-tab' && typeof onMyPaymentsTabOpened === 'function') {
                onMyPaymentsTabOpened();
            }
            if (tabId === 'draw-tab' && typeof loadAllDrawStats === 'function') {
                loadAllDrawStats(false);
            }
            if (tabId === 'cycles-tab' && typeof onCyclesTabOpened === 'function') {
                onCyclesTabOpened();
            }
        }

        // --- Payment & Offline Logic ---
        const catSel = document.getElementById('category_select');
        const subSel = document.getElementById('subscriber_select');
        const form = document.getElementById('payment-form');
        const alertBox = document.getElementById('message-alert');
        const SUBSCRIBER_CACHE_KEY = 'staffSubscriberCache';

        let subscriberCache = {};
        try {
            subscriberCache = JSON.parse(localStorage.getItem(SUBSCRIBER_CACHE_KEY) || '{}');
        } catch (e) {
            subscriberCache = {};
        }

        function saveSubscriberCache() {
            localStorage.setItem(SUBSCRIBER_CACHE_KEY, JSON.stringify(subscriberCache));
        }

        function setSubscriberOptions(subscribers, fallbackMessage = null) {
            subSel.innerHTML = '';
            if (!subscribers || subscribers.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = fallbackMessage || '-- لا يوجد مشتركين --';
                subSel.appendChild(option);
                subSel.disabled = true;
                return;
            }
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '-- اختر مشترك --';
            subSel.appendChild(defaultOption);
            subscribers.forEach(s => {
                const op = document.createElement('option');
                op.value = s.id;
                op.textContent = `${s.number} - ${s.name}`;
                subSel.appendChild(op);
            });
            subSel.disabled = false;
        }

        async function loadSubscribers(categoryName) {
            setSubscriberOptions([], '-- جاري التحميل --');
            if (!categoryName) {
                setSubscriberOptions([], '-- اختر فئة أولاً --');
                return;
            }

            if (!navigator.onLine) {
                const cached = subscriberCache[categoryName] || [];
                if (cached.length > 0) {
                    setSubscriberOptions(cached);
                    showAlert('أنت حالياً بدون اتصال، يتم عرض المشتركين من الذاكرة المؤقتة.', 'success');
                } else {
                    setSubscriberOptions([], 'لا يوجد بيانات للمشتركين بدون اتصال');
                    showAlert('لا يمكن تحميل قائمة المشتركين دون اتصال بالإنترنت.', 'danger');
                }
                return;
            }

            try {
                const res = await fetch(`/api/staff/subscribers/${encodeURIComponent(categoryName)}`);
                if (!res.ok) throw new Error('فشل في جلب المشتركين');
                const data = await res.json();
                if (Array.isArray(data)) {
                    subscriberCache[categoryName] = data;
                    saveSubscriberCache();
                }
                setSubscriberOptions(data, '-- لا يوجد مشتركين --');
            } catch (error) {
                const cached = subscriberCache[categoryName] || [];
                if (cached.length > 0) {
                    setSubscriberOptions(cached);
                    showAlert('حدث خطأ في الشبكة، تم عرض المشتركين من الذاكرة المؤقتة.', 'success');
                } else {
                    setSubscriberOptions([], 'فشل تحميل المشتركين');
                    showAlert('حدث خطأ أثناء تحميل المشتركين.', 'danger');
                }
            }
        }

        if (catSel) {
            catSel.addEventListener('change', async () => {
                const duesBox = document.getElementById('sub-dues-info');
                if (duesBox) duesBox.style.display = 'none';
                await loadSubscribers(catSel.value);
            });
        }

        if (subSel) {
            subSel.addEventListener('change', async () => {
                const duesBox = document.getElementById('sub-dues-info');
                const subId = subSel.value;
                if (!subId) {
                    if (duesBox) duesBox.style.display = 'none';
                    return;
                }

                if (!navigator.onLine) {
                    if (duesBox) duesBox.style.display = 'none';
                    return;
                }

                try {
                    const res = await fetch(`/api/staff/subscriber-info/${subId}`);
                    if (res.ok) {
                        const data = await res.json();
                        if (duesBox) {
                            document.getElementById('info-cat-amount').textContent = `${(data.category_amount || 0).toLocaleString()} ر.ي`;
                            if (data.next_installment) {
                                document.getElementById('info-next-inst').textContent = `دورة ${data.next_installment.cycle} / قسط ${data.next_installment.installment} (${(data.next_installment.amount || 0).toLocaleString()} ر.ي)`;
                            } else {
                                document.getElementById('info-next-inst').textContent = '✅ مسدد بالكامل حتى اليوم';
                            }
                            document.getElementById('info-overdue').textContent = `${data.overdue_count || 0} قسط`;
                            document.getElementById('info-total-unpaid').textContent = `${(data.total_unpaid || 0).toLocaleString()} ر.ي`;
                            duesBox.style.display = 'block';
                        }

                        // اقتراح مبلغ القسط تلقائياً لتسهيل العمل وتفادي الأخطاء
                        const amountInput = form ? form.querySelector('input[name="amount"]') : null;
                        if (amountInput && (!amountInput.value || parseFloat(amountInput.value) <= 0)) {
                            if (data.next_installment && data.next_installment.amount > 0) {
                                amountInput.value = data.next_installment.amount;
                            } else if (data.category_amount > 0) {
                                amountInput.value = data.category_amount;
                            }
                        }
                    }
                } catch (e) {
                    if (duesBox) duesBox.style.display = 'none';
                }
            });
        }

        async function sendPayment(payload) {
            const formData = new FormData();
            formData.append('subscriber_id', payload.subscriber_id);
            formData.append('amount', payload.amount);
            formData.append('note', payload.note || '');
            formData.append('client_reference', payload.client_reference);

            return await fetch('/staff/submit-payment', {
                method: 'POST',
                body: formData
            });
        }

        async function syncPendingPayments() {
            const queue = localStorage.getItem('staffPaymentQueue');
            if (!queue) return;
            let payments;
            try {
                payments = JSON.parse(queue);
                if (!Array.isArray(payments) || payments.length === 0) {
                    localStorage.removeItem('staffPaymentQueue');
                    return;
                }
            } catch (e) {
                localStorage.removeItem('staffPaymentQueue');
                return;
            }

            try {
                const res = await fetch('/staff/sync-payments', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({payments})
                });
                if (res.ok) {
                    localStorage.removeItem('staffPaymentQueue');
                    const data = await res.json();
                    showAlert(data.message || 'تم مزامنة المدفوعات المعلقة بنجاح', 'success');
                    return true;
                }
            } catch (e) {
                return false;
            }
            return false;
        }

        function queuePayment(payment) {
            const queue = localStorage.getItem('staffPaymentQueue');
            let payments = [];
            try {
                payments = queue ? JSON.parse(queue) : [];
            } catch (e) {
                payments = [];
            }
            payments.push(payment);
            localStorage.setItem('staffPaymentQueue', JSON.stringify(payments));
        }

        function showAlert(message, type) {
            if (!alertBox) return;
            alertBox.textContent = message;
            alertBox.className = 'alert ' + (type === 'success' ? 'alert-success' : 'alert-danger');
            alertBox.style.display = 'block';
        }

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                alertBox.style.display = 'none';

                const submitBtn = form.querySelector('button[type="submit"]');
                const origBtnText = submitBtn ? submitBtn.innerHTML : '';

                const formData = new FormData(form);
                const payload = {
                    subscriber_id: Number(formData.get('subscriber_id')),
                    amount: parseFloat(formData.get('amount')),
                    note: formData.get('note') || '',
                    client_reference: `staff-${Date.now()}-${Math.random().toString(36).slice(2)}`
                };

                if (!payload.subscriber_id || !payload.amount || payload.amount <= 0) {
                    showAlert('يرجى اختيار المشترك وإدخال مبلغ صحيح أكبر من صفر.', 'danger');
                    return;
                }

                // تعطيل زر الإرسال فوراً لمنع النقرات المزدوجة والتسديد المكرر
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span>⏳</span> جاري معالجة وتأكيد السداد...';
                }

                try {
                    const res = await sendPayment(payload);
                    const data = await res.json();
                    if (res.ok) {
                        showAlert(data.message || 'تم تسجيل السداد بنجاح', 'success');
                        form.reset();
                        subSel.disabled = true;
                        subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                        const duesBox = document.getElementById('sub-dues-info');
                        if (duesBox) duesBox.style.display = 'none';
                        await syncPendingPayments();
                    } else {
                        if (!navigator.onLine) {
                            queuePayment(payload);
                            showAlert('تم حفظ السداد مؤقتاً وسيتم إرساله تلقائياً عند العودة للإنترنت', 'success');
                            form.reset();
                            subSel.disabled = true;
                            subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                            const duesBox = document.getElementById('sub-dues-info');
                            if (duesBox) duesBox.style.display = 'none';
                        } else {
                            showAlert(data.message || 'حدث خطأ أثناء تسجيل السداد', 'danger');
                        }
                    }
                } catch (err) {
                    queuePayment(payload);
                    showAlert('تم حفظ السداد في قائمة الانتظار وسيتم إرساله عند استقرار الاتصال', 'success');
                    form.reset();
                    subSel.disabled = true;
                    subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                    const duesBox = document.getElementById('sub-dues-info');
                    if (duesBox) duesBox.style.display = 'none';
                } finally {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = origBtnText;
                    }
                }
            });
        }

        window.addEventListener('online', syncPendingPayments);
        window.addEventListener('load', () => {
            if (navigator.onLine) syncPendingPayments();
        });

        // --- My Payments Reconciliation Tab Logic ---
        let _mpInitialized = false;
        let _mpSearchTimer = null;
        let _mpLastRows = [];
        let _mpIsManager = false;

        function _mpEscapeHtml(str) {
            return String(str ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function _mpFormatMoney(num) {
            const val = Number(num || 0);
            return val.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + ' ر.ي';
        }

        function _mpIsoDate(d) {
            const y = d.getFullYear();
            const m = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${y}-${m}-${day}`;
        }

        function onMyPaymentsTabOpened() {
            if (!_mpInitialized) {
                _mpInitialized = true;
                const todayBtn = document.querySelector('#mp-quick-presets .mp-preset-btn[data-preset="today"]');
                applyMyPaymentsPreset('today', todayBtn);
            } else {
                loadMyPayments();
            }
        }

        function clearMyPaymentsPresetActive() {
            document.querySelectorAll('#mp-quick-presets .mp-preset-btn').forEach(b => {
                b.classList.remove('btn-primary');
                b.classList.add('btn-outline');
            });
        }

        function applyMyPaymentsPreset(preset, btn) {
            clearMyPaymentsPresetActive();
            if (btn) {
                btn.classList.remove('btn-outline');
                btn.classList.add('btn-primary');
            }
            const fromEl = document.getElementById('mp-date-from');
            const toEl = document.getElementById('mp-date-to');
            const now = new Date();
            const todayStr = _mpIsoDate(now);

            if (preset === 'today') {
                if (fromEl) fromEl.value = todayStr;
                if (toEl) toEl.value = todayStr;
            } else if (preset === 'yesterday') {
                const y = new Date(now);
                y.setDate(y.getDate() - 1);
                const yStr = _mpIsoDate(y);
                if (fromEl) fromEl.value = yStr;
                if (toEl) toEl.value = yStr;
            } else if (preset === 'week') {
                const w = new Date(now);
                w.setDate(w.getDate() - 6);
                if (fromEl) fromEl.value = _mpIsoDate(w);
                if (toEl) toEl.value = todayStr;
            } else if (preset === 'month') {
                const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
                if (fromEl) fromEl.value = _mpIsoDate(firstDay);
                if (toEl) toEl.value = todayStr;
            } else {
                if (fromEl) fromEl.value = '';
                if (toEl) toEl.value = '';
            }
            loadMyPayments();
        }

        function filterMyPaymentsByDay(dateStr) {
            if (!dateStr || dateStr === 'غير محدد') return;
            clearMyPaymentsPresetActive();
            const fromEl = document.getElementById('mp-date-from');
            const toEl = document.getElementById('mp-date-to');
            if (fromEl) fromEl.value = dateStr;
            if (toEl) toEl.value = dateStr;
            loadMyPayments();
        }

        function filterMyPaymentsByStaff(staffKey) {
            const sel = document.getElementById('mp-staff-filter');
            if (sel) {
                sel.value = staffKey || 'all';
            }
            loadMyPayments();
        }

        function debounceMyPaymentsSearch() {
            clearTimeout(_mpSearchTimer);
            _mpSearchTimer = setTimeout(() => loadMyPayments(), 300);
        }

        async function loadMyPayments() {
            const tbody = document.getElementById('mp-payments-tbody');
            const dailyTbody = document.getElementById('mp-daily-tbody');
            const staffTbody = document.getElementById('mp-staff-summary-tbody');
            const staffFilterEl = document.getElementById('mp-staff-filter');
            if (!tbody) return;

            const dateFrom = document.getElementById('mp-date-from')?.value || '';
            const dateTo = document.getElementById('mp-date-to')?.value || '';
            const category = document.getElementById('mp-category')?.value || 'الكل';
            const search = document.getElementById('mp-search')?.value || '';
            const filterStaffId = staffFilterEl ? (staffFilterEl.value || 'all') : '';

            const params = new URLSearchParams();
            if (dateFrom) params.set('date_from', dateFrom);
            if (dateTo) params.set('date_to', dateTo);
            if (category && category !== 'الكل') params.set('category', category);
            if (search.trim()) params.set('search', search.trim());
            if (filterStaffId && filterStaffId !== 'all') params.set('filter_staff_id', filterStaffId);

            const colSpan = staffFilterEl ? 9 : 8;
            tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center;color:var(--text-muted);padding:24px;">جاري تحميل سجل التسديدات...</td></tr>`;

            try {
                const res = await fetch(`/api/staff/my-payments?${params.toString()}`);
                if (!res.ok) throw new Error('فشل جلب سجل التسديدات');
                const data = await res.json();
                if (!data.success) throw new Error(data.message || 'تعذر تحميل البيانات');

                _mpIsManager = Boolean(data.is_manager);

                // تحديث قائمة الموظفين في الفلتر وجدول ملخص الموظفين (للمدير فقط)
                if (_mpIsManager && staffFilterEl && Array.isArray(data.staff_list)) {
                    const prevVal = staffFilterEl.value || 'all';
                    staffFilterEl.innerHTML = '<option value="all">كل الموظفين</option>' +
                        data.staff_list.map(st =>
                            `<option value="${_mpEscapeHtml(st.key)}">${_mpEscapeHtml(st.name)} (${_mpEscapeHtml(st.role)})</option>`
                        ).join('');
                    staffFilterEl.value = prevVal;
                    if (!staffFilterEl.value) staffFilterEl.value = 'all';
                }

                if (_mpIsManager && staffTbody) {
                    const stRows = data.staff_summary || [];
                    const stBadge = document.getElementById('mp-staff-count-badge');
                    if (stBadge) stBadge.textContent = `${stRows.length} موظف`;
                    const activeKey = staffFilterEl ? staffFilterEl.value : 'all';

                    if (stRows.length === 0) {
                        staffTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:16px;">لا يوجد موظفون مسجلون.</td></tr>';
                    } else {
                        staffTbody.innerHTML = stRows.map(st => {
                            const isSelected = activeKey === st.staff_key;
                            const rowBg = isSelected ? 'background:#eff6ff;' : '';
                            return `
                                <tr style="cursor:pointer;${rowBg}" onclick="filterMyPaymentsByStaff('${_mpEscapeHtml(st.staff_key)}')">
                                    <td style="font-weight:800;color:#0f172a;">
                                        👤 ${_mpEscapeHtml(st.staff_name)}
                                        <span style="font-size:0.74rem;background:#f1f5f9;color:#475569;padding:2px 7px;border-radius:999px;margin-right:4px;">${_mpEscapeHtml(st.staff_role)}</span>
                                    </td>
                                    <td style="font-weight:800;color:#059669;">
                                        ${_mpFormatMoney(st.today_amount)}
                                        <div style="font-size:0.74rem;color:#64748b;font-weight:600;">${st.today_subscribers} مشترك • ${st.today_payments} قسط</div>
                                    </td>
                                    <td><span style="background:#ede9fe;color:#5b21b6;padding:3px 10px;border-radius:999px;font-weight:700;font-size:0.82rem;">${st.unique_subscribers} مشترك</span></td>
                                    <td style="font-weight:700;">${st.payments_count} قسط</td>
                                    <td style="font-weight:900;color:#2563eb;">${_mpFormatMoney(st.total_amount)}</td>
                                    <td>
                                        <button type="button" class="btn-compact ${isSelected ? 'btn-primary' : 'btn-outline'}" style="height:28px;font-size:0.78rem;padding:0 10px;" onclick="event.stopPropagation(); filterMyPaymentsByStaff('${_mpEscapeHtml(st.staff_key)}')">
                                            ${isSelected ? '✓ معروض الآن' : 'عرض تفاصيله'}
                                        </button>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                const s = data.summary || {};
                const elTodayAmt = document.getElementById('mp-today-amount');
                const elTodayMeta = document.getElementById('mp-today-meta');
                const elTotalAmt = document.getElementById('mp-total-amount');
                const elUniqueSubs = document.getElementById('mp-unique-subs');
                const elPayCount = document.getElementById('mp-payments-count');

                if (elTodayAmt) elTodayAmt.textContent = _mpFormatMoney(s.today_amount || 0);
                if (elTodayMeta) elTodayMeta.textContent = `${s.today_subscribers || 0} مشترك • ${s.today_payments || 0} عملية`;
                if (elTotalAmt) elTotalAmt.textContent = _mpFormatMoney(s.total_amount || 0);
                if (elUniqueSubs) elUniqueSubs.textContent = String(s.unique_subscribers || 0);
                if (elPayCount) elPayCount.textContent = String(s.payments_count || 0);

                // ملخص التحصيل اليومي
                const daily = data.daily_summary || [];
                const daysBadge = document.getElementById('mp-days-count-badge');
                if (daysBadge) daysBadge.textContent = `${daily.length} يوم`;

                if (dailyTbody) {
                    if (daily.length === 0) {
                        dailyTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:16px;">لا توجد تسديدات في الفترة المحددة.</td></tr>';
                    } else {
                        dailyTbody.innerHTML = daily.map(d => `
                            <tr style="cursor:pointer;" onclick="filterMyPaymentsByDay('${_mpEscapeHtml(d.date)}')">
                                <td style="font-weight:800;color:#0f172a;">📅 ${_mpEscapeHtml(d.date)}</td>
                                <td><span style="background:#ede9fe;color:#5b21b6;padding:3px 10px;border-radius:999px;font-weight:700;font-size:0.82rem;">${d.unique_subscribers} مشترك</span></td>
                                <td style="font-weight:700;">${d.payments_count} قسط</td>
                                <td style="font-weight:900;color:#059669;">${_mpFormatMoney(d.total_amount)}</td>
                                <td><button type="button" class="btn-compact btn-outline" style="height:28px;font-size:0.78rem;padding:0 10px;" onclick="event.stopPropagation(); filterMyPaymentsByDay('${_mpEscapeHtml(d.date)}')">عرض هذا اليوم</button></td>
                            </tr>
                        `).join('');
                    }
                }

                // جدول تفاصيل التسديدات
                const rows = data.payments || [];
                _mpLastRows = rows;
                const rowsBadge = document.getElementById('mp-rows-count-badge');
                if (rowsBadge) rowsBadge.textContent = `إجمالي السجلات: ${rows.length}`;

                if (rows.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center;color:var(--text-muted);padding:26px;">لا توجد عمليات تسديد مطابقة للفلتر المحدد.</td></tr>`;
                } else {
                    tbody.innerHTML = rows.map((r, idx) => `
                        <tr>
                            <td style="font-weight:700;color:var(--text-muted);">${idx + 1}</td>
                            <td style="font-weight:800;color:#0f172a;">${_mpEscapeHtml(r.subscriber_name)}</td>
                            <td><span style="background:#f1f5f9;color:#1e293b;padding:2px 8px;border-radius:6px;font-weight:800;">#${_mpEscapeHtml(r.subscriber_number)}</span></td>
                            <td>${_mpEscapeHtml(r.category)}</td>
                            <td style="font-weight:700;">قسط ${r.installment_number} / دورة ${r.cycle_number}</td>
                            <td style="font-weight:900;color:#059669;">${_mpFormatMoney(r.amount)}</td>
                            ${_mpIsManager ? `<td style="font-weight:700;color:#1e40af;">${_mpEscapeHtml(r.staff_name || '-')}</td>` : ''}
                            <td style="direction:ltr;text-align:center;font-weight:600;color:#334155;">${_mpEscapeHtml(r.paid_datetime_str)}</td>
                            <td style="color:var(--text-muted);font-size:0.84rem;">${_mpEscapeHtml(r.note)}</td>
                        </tr>
                    `).join('');
                }
            } catch (err) {
                tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align:center;color:#dc2626;padding:20px;">${_mpEscapeHtml(err.message || 'حدث خطأ أثناء تحميل السجل')}</td></tr>`;
            }
        }

        function exportMyPaymentsCSV() {
            if (!_mpLastRows || _mpLastRows.length === 0) {
                alert('لا توجد بيانات لتصديرها حالياً.');
                return;
            }
            const headers = _mpIsManager
                ? ['#', 'اسم المشترك', 'رقم الحساب', 'رقم الهاتف', 'الفئة', 'القسط', 'الدورة', 'المبلغ', 'الموظف المحصل', 'تاريخ ووقت التسديد', 'الملاحظة']
                : ['#', 'اسم المشترك', 'رقم الحساب', 'رقم الهاتف', 'الفئة', 'القسط', 'الدورة', 'المبلغ', 'تاريخ ووقت التسديد', 'الملاحظة'];
            const lines = [headers.join(',')];
            _mpLastRows.forEach((r, idx) => {
                const baseVals = [
                    idx + 1,
                    r.subscriber_name,
                    r.subscriber_number,
                    r.subscriber_phone,
                    r.category,
                    r.installment_number,
                    r.cycle_number,
                    r.amount,
                ];
                if (_mpIsManager) baseVals.push(r.staff_name || '-');
                baseVals.push(r.paid_datetime_str, r.note);
                const vals = baseVals.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`);
                lines.push(vals.join(','));
            });
            const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const dFrom = document.getElementById('mp-date-from')?.value || 'all';
            const dTo = document.getElementById('mp-date-to')?.value || 'all';
            a.href = url;
            a.download = `my_payments_${dFrom}_${dTo}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }