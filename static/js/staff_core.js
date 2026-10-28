/* staff_core.js - منطق التبويب والدفعات الأساسي - مستخرج تلقائياً */

// --- Tab Switching Logic ---
        function switchMainTab(tabId, btn) {
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
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
                await loadSubscribers(catSel.value);
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

                const formData = new FormData(form);
                const payload = {
                    subscriber_id: Number(formData.get('subscriber_id')),
                    amount: parseFloat(formData.get('amount')),
                    note: formData.get('note') || '',
                    client_reference: `offline-${Date.now()}-${Math.random().toString(36).slice(2)}`
                };

                if (!payload.subscriber_id || !payload.amount) {
                    showAlert('يرجى اختيار المشترك والمبلغ قبل الإرسال.', 'danger');
                    return;
                }

                try {
                    const res = await sendPayment(payload);
                    const data = await res.json();
                    if (res.ok) {
                        showAlert(data.message || 'تم تسجيل السداد بنجاح', 'success');
                        form.reset();
                        subSel.disabled = true;
                        subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                        await syncPendingPayments();
                    } else {
                        if (!navigator.onLine) {
                            queuePayment(payload);
                            showAlert('تم حفظ السداد مؤقتاً وسيتم إرساله عند العودة للإنترنت', 'success');
                            form.reset();
                            subSel.disabled = true;
                            subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                        } else {
                            showAlert(data.message || 'حدث خطأ أثناء تسجيل السداد', 'danger');
                        }
                    }
                } catch (err) {
                    queuePayment(payload);
                    showAlert('تم حفظ السداد مؤقتاً وسيتم إرساله عند العودة للإنترنت', 'success');
                    form.reset();
                    subSel.disabled = true;
                    subSel.innerHTML = '<option value="">-- اختر مشترك --</option>';
                }
            });
        }

        window.addEventListener('online', syncPendingPayments);
        window.addEventListener('load', () => {
            if (navigator.onLine) syncPendingPayments();
        });