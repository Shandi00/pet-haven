import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from 'react-query';
import { ChevronDown, ChevronUp, Gamepad2 } from 'lucide-react';
import { Button, Skeleton } from './ui';
import PetTypeCard from './PetTypeCard';
import ProfileSettingsForm from './ProfileSettingsForm';
import { matchingAPI } from '../services/api';

// 個人中心「配對檔案」分頁（T09）：遊戲結果優先，配對檔案表單預設收起
const MatchingProfileTab = () => {
  const navigate = useNavigate();
  const [formOpen, setFormOpen] = useState(false);
  // cacheTime 0：每次進到分頁都重新讀取。ProfileSettingsForm 只在掛載時讀 initialData，
  // 用到快取的舊資料時，剛玩完遊戲寫入的欄位會被表單裡的舊值蓋回去
  const { data: profile, isLoading, error, refetch } = useQuery(
    'matchingProfile',
    async () => (await matchingAPI.getProfile()).data.data,
    { cacheTime: 0 }
  );

  if (isLoading) {
    return (
      <div className="space-y-4" role="status" aria-label="載入中">
        <Skeleton variant="rect" height="12rem" />
        <Skeleton variant="rect" height="3rem" />
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="text-center py-12 text-red-600">
        {error.response?.data?.message || '載入失敗，請稍後再試'}
      </div>
    );
  }

  // gameProfile 是 null，或回應沒有這個欄位（後端計畫 Task 4 完成前），都當成沒玩過
  const petType = profile?.gameProfile?.petType?.label ? profile.gameProfile.petType : null;
  const goToGame = () => navigate('/match-game');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">配對檔案</h2>
        <p className="mt-1 text-sm text-gray-600">推薦會依照這裡的生活方式、養寵物經驗與家庭環境計算</p>
      </div>

      <div className="bg-gray-50 rounded-lg p-6">
        {petType ? (
          <PetTypeCard petType={petType} className="py-2">
            <Button onClick={goToGame} className="mt-6 inline-flex items-center gap-2">
              <Gamepad2 className="w-5 h-5" aria-hidden="true" />
              再玩一次
            </Button>
          </PetTypeCard>
        ) : (
          <div className="flex flex-col items-center text-center py-2">
            <p className="text-gray-600">回答幾個生活情境問題，找出適合你的毛孩類型，並自動填好配對檔案。</p>
            <Button onClick={goToGame} className="mt-4 inline-flex items-center gap-2">
              <Gamepad2 className="w-5 h-5" aria-hidden="true" />
              去玩配對遊戲
            </Button>
          </div>
        )}
      </div>

      <div>
        <Button
          variant="outline"
          aria-expanded={formOpen}
          aria-controls="matching-profile-form"
          onClick={() => setFormOpen((open) => !open)}
          className="inline-flex items-center gap-2"
        >
          {formOpen ? <ChevronUp className="w-5 h-5" aria-hidden="true" /> : <ChevronDown className="w-5 h-5" aria-hidden="true" />}
          手動修改配對檔案
        </Button>

        {formOpen && (
          <div id="matching-profile-form" className="mt-4 animate-fade-in">
            <p className="text-sm text-gray-500">想改其中一項，不用重玩遊戲，直接在這裡修改</p>
            <ProfileSettingsForm initialData={profile} onSave={() => refetch()} bare />
          </div>
        )}
      </div>
    </div>
  );
};

export default MatchingProfileTab;
