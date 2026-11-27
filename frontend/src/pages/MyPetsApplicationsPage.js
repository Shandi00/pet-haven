import React, { useState, useEffect } from 'react';
import ApplicationDetailModal from '../components/ApplicationDetailModal';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../services/auth';
import { adoptionAPI } from '../services/api';
import toast from 'react-hot-toast';
import { CheckCircle, XCircle, Clock, Eye, Home } from 'lucide-react';
import { Button, Modal, Pagination, Textarea } from '../components/ui';

const PAGE_SIZE = 10;
const REJECT_REASON_MAX = 200;
// 拒絕時可以直接點選的常用原因，點了會填進輸入框，還可以再修改
const REJECT_REASONS = ['居住環境不適合這隻動物', '照顧時間不足', '已有其他更適合的認養人', '申請資料不完整'];

const MyPetsApplicationsPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const location = useLocation();
  
  // 從 URL 參數讀取初始篩選條件
  const initialFilter = React.useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('filter') || 'all';
  }, [location.search]);
  
  const [filter, setFilter] = useState(initialFilter);
  const [page, setPage] = useState(1);

  // 此頁面應顯示「我發布的寵物收到的申請」；即便是 admin 帳號也只看自己發布的寵物
  const apiEndpoint = '/api/adoptions/my-pets-applications';

  // 獲取收到的申請列表；後端每頁 10 筆，沒帶 page 只會拿到前 10 筆
  const { data, isLoading, isError } = useQuery(
    ['myPetsApplications', filter, user?._id, page],
    async () => {
      const token = localStorage.getItem('token');
      const statusParam = filter !== 'all' ? `&status=${filter}` : '';
      const response = await fetch(`http://localhost:5000${apiEndpoint}?page=${page}&limit=${PAGE_SIZE}${statusParam}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) throw new Error('載入失敗');
      return response.json();
    },
    { keepPreviousData: true }  // 換頁或篩選時保留上一頁內容，不會整頁變成載入中
  );
  const changeFilter = (next) => {
    setFilter(next);
    setPage(1);
  };
  const changePage = (next) => {
    setPage(next);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // 審核申請
  const reviewMutation = useMutation(
    async ({ id, decision, reason }) => {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:5000/api/adoptions/${id}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ decision, reason })
      });
      const body = await response.json().catch(() => ({}));
      // 顯示後端的原因（例如動物已被認養不能再核准）
      if (!response.ok) throw new Error(body.error || '審核失敗，請稍後再試');
      return body;
    },
    {
      onSuccess: () => {
        toast.success('審核完成');
        queryClient.invalidateQueries(['myPetsApplications']);
      },
      onError: (error) => {
        toast.error(error.message);
      }
    }
  );

  // 拒絕要先在視窗填原因（申請人會在通知看到）；成功才關閉視窗，失敗時保留填好的內容
  const [rejecting, setRejecting] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const openReject = (app) => {
    setRejecting(app);
    setRejectReason('');
  };
  const closeReject = () => {
    if (!reviewMutation.isLoading) setRejecting(null);
  };
  const submitReject = () => {
    const reason = rejectReason.trim();
    if (!reason) return;
    reviewMutation.mutate({ id: rejecting._id, decision: 'rejected', reason }, { onSuccess: () => setRejecting(null) });
  };

  // 完成認養：已通過的申請交付後按下，寵物會改成已被認養
  const completeMutation = useMutation((id) => adoptionAPI.completeAdoption(id, {}), {
    onSuccess: () => {
      toast.success('已完成認養');
      queryClient.invalidateQueries(['myPetsApplications']);
    },
    onError: (error) => {
      toast.error(error.response?.data?.error || '完成認養失敗，請稍後再試');
    }
  });

  const [completing, setCompleting] = useState(null);
  const closeComplete = () => {
    if (!completeMutation.isLoading) setCompleting(null);
  };
  const submitComplete = () => {
    completeMutation.mutate(completing._id, { onSuccess: () => setCompleting(null) });
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: { text: '待審核', color: 'bg-yellow-100 text-yellow-800', icon: Clock },
      'under-review': { text: '審核中', color: 'bg-blue-100 text-blue-800', icon: Clock },
      approved: { text: '已通過', color: 'bg-green-100 text-green-800', icon: CheckCircle },
      completed: { text: '已完成', color: 'bg-primary-100 text-primary-800', icon: CheckCircle },
      rejected: { text: '已拒絕', color: 'bg-red-100 text-red-800', icon: XCircle },
      cancelled: { text: '已取消', color: 'bg-gray-100 text-gray-800', icon: XCircle }
    };
    const badge = badges[status] || badges.pending;
    const Icon = badge.icon;
    return (
      <span className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap px-3 py-1 rounded-full text-sm font-medium ${badge.color}`}>
        <Icon className="w-4 h-4" />
        {badge.text}
      </span>
    );
  };

  const applications = data?.data?.applications || [];
  const totalPages = data?.data?.pagination?.totalPages || 0;
  // 審核後最後一頁可能變空（例如在「待審核」把最後一筆拒絕了），退回到還有資料的最後一頁
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    if (!location) return;
    try {
      const params = new URLSearchParams(location.search);
      const applicationId = params.get('applicationId');
      if (applicationId) {
        setSelectedApplicationId(applicationId);
        setIsModalOpen(true);
      }
    } catch (e) {
      // ignore
    }
  }, [location && location.search]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
            <p className="mt-4 text-gray-600">載入中...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* 頁面標題 */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">收到的認養申請</h1>
          <p className="mt-2 text-gray-600">管理您發布的寵物收到的認養申請</p>
        </div>

        {/* 篩選器 */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex flex-wrap gap-2">
            {['all', 'pending', 'approved', 'completed', 'rejected'].map((status) => (
              <button
                key={status}
                onClick={() => changeFilter(status)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filter === status
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {status === 'all' && '全部'}
                {status === 'pending' && '待審核'}
                {status === 'approved' && '已通過'}
                {status === 'completed' && '已完成'}
                {status === 'rejected' && '已拒絕'}
              </button>
            ))}
          </div>
        </div>

        {/* 申請列表 */}
        {isError ? (
          <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-6 text-center text-red-600">
            載入失敗，請稍後再試
          </div>
        ) : applications.length > 0 ? (
          <div className="grid gap-6">
            {applications.map((app) => (
              <div key={app._id} className="bg-white rounded-lg shadow-sm p-4 sm:p-6">
                <div className="flex flex-col sm:flex-row gap-4 sm:gap-6">
                  {/* 寵物照片 */}
                    <div className="flex-shrink-0">
                    <img
                      src={(() => {
                        const pet = app.pet || {};
                        if (pet.primaryPhoto && pet.primaryPhoto.url) return pet.primaryPhoto.url;
                        if (Array.isArray(pet.photos) && pet.photos.length > 0) {
                          const first = pet.photos[0];
                          if (typeof first === 'string') return first;
                          if (first.url) return first.url;
                          if (first.filename) return `/uploads/pets/${first.filename}`;
                        }
                        if (Array.isArray(pet.images) && pet.images.length > 0) return pet.images[0];
                        return '/placeholder-pet.jpg';
                      })()}
                      alt={app.pet?.name}
                      className="w-full h-48 sm:w-32 sm:h-32 object-cover rounded-lg"
                    />
                  </div>

                  {/* 申請資訊 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3 mb-4">
                      <div className="min-w-0">
                        <h3 className="text-xl font-bold text-gray-900">{app.pet?.name}</h3>
                        <p className="text-gray-600 break-all">申請者: {app.applicant?.username}</p>
                      </div>
                      {getStatusBadge(app.status)}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-4 text-sm mb-4">
                      <div>
                        <span className="text-gray-500">申請日期:</span>
                        <span className="ml-2 text-gray-900">{(() => {
                          const candidates = [app.submittedAt, app.createdAt, app.agreementDate];
                          for (const c of candidates) {
                            if (!c) continue;
                            const d = new Date(c);
                            if (!isNaN(d.getTime())) return d.toLocaleDateString('zh-TW');
                          }
                          return '未知';
                        })()}</span>
                      </div>
                      {(() => {
                          // 使用與 ApplicationDetailModal 相同的候選優先順序：
                          // applicantDetails.contact.phone, applicantDetails.contactPhone, personalInfo.phone, contactInfo.phone, applicant.phone
                          const candidates = [
                            app.applicantDetails?.contact?.phone,
                            app.applicantDetails?.contactPhone,
                            app.personalInfo?.contact?.phone,
                            app.personalInfo?.phone,
                            app.contactInfo?.phone,
                            app.applicant?.phone
                          ];
                          // rawSubmission (若存在) 作為最後 fallback
                          if (app.rawSubmission) {
                            candidates.push(
                              app.rawSubmission?.applicantDetails?.contact?.phone,
                              app.rawSubmission?.applicantDetails?.contactPhone,
                              app.rawSubmission?.contactInfo?.phone,
                              app.rawSubmission?.contactPhone
                            );
                          }

                          let phone = null;
                          for (const c of candidates) {
                            if (typeof c === 'string' && c.trim()) { phone = c.trim(); break; }
                            if (typeof c === 'number') { phone = String(c); break; }
                          }

                          return phone ? (
                            <div>
                              <span className="text-gray-500">聯絡電話:</span>
                              <span className="ml-2 text-gray-900">{phone}</span>
                            </div>
                          ) : null;
                        })()}
                    </div>

                    {/* 操作按鈕 */}
                      <div className="flex flex-wrap gap-3">
                      {app.status === 'pending' && (
                        <>
                          {app.pet?.adoptionStatus === 'adopted' ? (
                            <p className="w-full text-sm text-gray-600">{app.pet?.name} 已被認養，這份申請只能拒絕。</p>
                          ) : (
                            <button
                              onClick={() => reviewMutation.mutate({ id: app._id, decision: 'approved', reason: '' })}
                              disabled={reviewMutation.isLoading}
                              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors flex items-center gap-2"
                            >
                              <CheckCircle className="w-4 h-4" />
                              通過
                            </button>
                          )}
                          <button
                            onClick={() => openReject(app)}
                            disabled={reviewMutation.isLoading}
                            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors flex items-center gap-2"
                          >
                            <XCircle className="w-4 h-4" />
                            拒絕
                          </button>
                        </>
                      )}
                      {app.status === 'approved' && (
                        <button
                          onClick={() => setCompleting(app)}
                          disabled={completeMutation.isLoading}
                          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                        >
                          <Home className="w-4 h-4" />
                          完成認養
                        </button>
                      )}
                      <button
                        onClick={() => {
                          console.log('Attempt open application modal, id=', app._id);
                          // 權限檢查：只能由申請人、該寵物發布者 (createdBy) 或 admin 查看詳情
                          const me = user && user._id ? user._id : null;
                          const isApplicant = me && app.applicant && (app.applicant._id === me || app.applicant._id === me?.toString());
                          const petCreatorId = app.pet && app.pet.createdBy && (app.pet.createdBy._id || app.pet.createdBy);
                          const isPetOwner = me && petCreatorId && (petCreatorId === me || petCreatorId === me?.toString());
                          const isAdmin = user && (user.role === 'admin' || user.role === 'volunteer');

                          if (!isApplicant && !isPetOwner && !isAdmin) {
                            try { window.alert('您沒有權限查看此申請詳情。'); } catch(e){}
                            console.warn('Blocked opening application details due to insufficient permissions', { me, appId: app._id, appApplicant: app.applicant, petCreatorId });
                            return;
                          }

                          setSelectedApplicationId(app._id);
                          setIsModalOpen(true);
                        }}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center gap-2"
                      >
                        <Eye className="w-4 h-4" />
                        查看申請詳情
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {totalPages > 1 && (
              <Pagination currentPage={page} totalPages={totalPages} onPageChange={changePage} className="pt-2" />
            )}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <Clock className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">暫無申請記錄</p>
          </div>
        )}
        {/* 申請詳情模態框 */}
        <ApplicationDetailModal
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedApplicationId(null);
          }}
          applicationId={selectedApplicationId}
        />

        <Modal
          isOpen={Boolean(rejecting)}
          onClose={closeReject}
          title={`拒絕 ${rejecting?.pet?.name || ''} 的申請`}
          size="sm"
          footer={(
            <>
              <Button variant="ghost" onClick={closeReject} disabled={reviewMutation.isLoading}>取消</Button>
              <Button variant="danger" onClick={submitReject} loading={reviewMutation.isLoading}
                disabled={!rejectReason.trim()}>
                確定拒絕
              </Button>
            </>
          )}
        >
          <p className="text-sm text-gray-600 mb-3">申請人會收到通知，並看到你填寫的原因。</p>
          <div className="flex flex-wrap gap-2 mb-3">
            {REJECT_REASONS.map((r) => (
              <button key={r} type="button" onClick={() => setRejectReason(r)}
                className="px-3 py-1 text-sm rounded-full border border-gray-300 text-gray-700 hover:bg-gray-100">
                {r}
              </button>
            ))}
          </div>
          <Textarea label="拒絕原因" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}
            maxLength={REJECT_REASON_MAX} rows={3} fullWidth
            helperText={`${rejectReason.length}/${REJECT_REASON_MAX} 字，可以點上方的常用原因再修改`} />
        </Modal>

        <Modal
          isOpen={Boolean(completing)}
          onClose={closeComplete}
          title="確認完成認養"
          size="sm"
          footer={(
            <>
              <Button variant="ghost" onClick={closeComplete} disabled={completeMutation.isLoading}>取消</Button>
              <Button onClick={submitComplete} loading={completeMutation.isLoading}>確認完成</Button>
            </>
          )}
        >
          <p className="text-gray-700">
            確定 <strong>{completing?.pet?.name}</strong> 已經交付給 <strong>{completing?.applicant?.username}</strong>？
          </p>
          <p className="mt-2 text-sm text-gray-600">完成後動物會標示為「已被認養」，這個動作無法復原。</p>
        </Modal>
      </div>
    </div>
  );
};

export default MyPetsApplicationsPage;
