import { useEffect } from 'react';
import { useAppSelector } from '@/store/AppStateStore';
import { clientApi } from '@/services/clientApi';

const PREFETCH_AHEAD = 10; // Number of frames to prefetch ahead
const PREFETCH_DELAY = 30; // Delay in milliseconds for prefetching

export function useFramePrefetcher() {
    const { currentFrame, totalFrames } = useAppSelector(state => state.playbackControl);
    
    useEffect(() => {
        // Clear any existing prefetch timeouts
        const timeouts: number[] = [];
        
        // Prefetch next frames with staggered timing
        for (let i = 1; i <= PREFETCH_AHEAD; i++) {
            const frameToFetch = currentFrame + i;
            if (frameToFetch < totalFrames) {
                const timeout = window.setTimeout(() => {
                    clientApi.util.prefetch('getFrames', { frameNumber: frameToFetch }, { force: false });
                }, i * PREFETCH_DELAY); // Stagger the requests
                
                timeouts.push(timeout);
            }
        }
        
        // Cleanup function to clear any pending timeouts
        return () => {
            timeouts.forEach(timeout => window.clearTimeout(timeout));
        };
    }, [currentFrame, totalFrames]);
}