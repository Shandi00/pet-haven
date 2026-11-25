const express = require('express');
const router = express.Router();
const Notification = require('../models/Notification');
const { auth, authorize } = require('../middleware/auth');

// 開發用：建立並發送測試通知
// 只在開發模式啟用，且限管理員，避免本機展示（development 模式）時任何人都能發通知
router.post('/emit', auth, authorize('admin'), async (req, res) => {
  if (process.env.NODE_ENV !== 'development') {
    return res.status(403).json({ error: 'Not allowed in non-development environment' });
  }

  try {
    const { recipient, relatedAdoption, title, content, type } = req.body;
    if (!recipient) return res.status(400).json({ error: 'recipient is required' });

    const notif = await Notification.createNotification({
      recipient,
      type: type || 'adoption_received',
      title: title || '測試通知',
      content: content || '這是開發用測試通知',
      link: relatedAdoption ? `/adoptions/${relatedAdoption}` : undefined,
      relatedAdoption: relatedAdoption || undefined
    });

    return res.json({ ok: true, id: notif._id });
  } catch (err) {
    console.error('Debug emit failed', err);
    return res.status(500).json({ error: err.message });
  }
});

module.exports = router;
