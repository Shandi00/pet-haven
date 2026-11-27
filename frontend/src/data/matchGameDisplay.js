import {
  Award, Baby, Building2, Cat, Clock, Crown, Heart, Home, Hourglass, Moon, Mountain, PawPrint, Shuffle, Sparkles,
  Trees, Tv, User, Volume2, VolumeX, Wind,
} from 'lucide-react';

// 配對小遊戲每個選項的圖示，以及選了之後小狗的回應。只影響畫面，不影響計分。
// 回應要和實際的配對規則一致，不能說做不到的事：小孩、其他寵物、對貓過敏是 Top 3 的硬條件
// （backend/app/services/top3.py），需要安靜會讓愛叫或好動的動物扣分（advanced_matching.py）。
// 題目有增減時要和 matchGameQuestions.js 一起改；matchGameDisplay.test.js 會檢查每個選項都有對應。
export const optionDisplay = {
  q1: {
    A: { icon: Mountain, reaction: '活力滿點！會優先找活動量高、愛出門的毛孩。' },
    B: { icon: Tv, reaction: '愛宅在家？會優先找個性安靜、不用常出門的毛孩。' },
    C: { icon: Shuffle, reaction: '能動能靜，選擇最多！' },
  },
  q2: {
    A: { icon: Hourglass, reaction: '時間很充裕，需要多陪伴的毛孩也沒問題。' },
    B: { icon: Clock, reaction: '每天一小時，剛剛好的陪伴。' },
    C: { icon: Moon, reaction: '忙碌也沒關係，會優先找比較能自己待著的毛孩。' },
  },
  q3: {
    A: { icon: Trees, reaction: '有院子！毛孩有地方跑跑跳跳了。' },
    B: { icon: Home, reaction: '空間夠大，在室內也能玩得開心。' },
    C: { icon: Building2, reaction: '住公寓也能養，選對個性最重要。' },
  },
  q4: {
    A: { icon: Award, reaction: '資深鏟屎官，經驗值滿點！' },
    B: { icon: Heart, reaction: '有經驗，很快就能上手。' },
    C: { icon: Sparkles, reaction: '第一次養也沒關係，會優先找適合新手的毛孩。' },
  },
  q5: {
    A: { icon: Baby, reaction: '會避開不適合和小孩相處的毛孩。' },
    B: { icon: User, reaction: '了解，下一題！' },
  },
  q6: {
    A: { icon: PawPrint, reaction: '會避開不喜歡其他寵物的毛孩。' },
    B: { icon: Crown, reaction: '牠可以獨享你全部的愛。' },
  },
  q7: {
    A: { icon: VolumeX, reaction: '愛叫或太好動的毛孩會排後面一點。' },
    B: { icon: Volume2, reaction: '好，叫聲不會影響推薦。' },
  },
  q8: {
    A: { icon: Wind, reaction: '收到，推薦時會先排除貓咪。' },
    B: { icon: Cat, reaction: '太好了，貓咪和狗狗都在名單裡！' },
  },
};

// 對應不到時（例如新增了題目卻忘了補）退回腳印圖示、不顯示回應，遊戲照樣能玩
export const displayFor = (questionId, optionId) =>
  optionDisplay[questionId]?.[optionId] || { icon: PawPrint, reaction: '' };
