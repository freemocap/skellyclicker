import {createSlice, PayloadAction} from '@reduxjs/toolkit';

export interface PlaybackControlState {
    isPlaying: boolean;
    currentFrame: number;
    stepSize: number;
    totalFrames: number;
    startFrame: number | null;
    endFrame: number | null;
}

const initialState: PlaybackControlState = {
    isPlaying: false,
    currentFrame: 0,
    stepSize: 1,
    totalFrames: 0,
    startFrame: null,
    endFrame: null,
};

export const playbackControlSlice = createSlice({
    name: 'playbackControl',
    initialState,
    reducers: {
        setIsPlaying: (state, action: PayloadAction<boolean>) => {
            state.isPlaying = action.payload;
        },
        setCurrentFrame: (state, action: PayloadAction<number>) => {
            // Ensure frame is within bounds
            state.currentFrame = Math.max(0, Math.min(action.payload, state.totalFrames - 1));
        },
        nextFrame: (state) => {
            const nextFrame = state.currentFrame + state.stepSize;
            if (nextFrame < state.totalFrames) {
                state.currentFrame = nextFrame;
            } else {
                // Loop back to beginning if we reach the end
                state.currentFrame = 0;
                state.isPlaying = false; // Stop playback when we reach the end
            }
        },
        previousFrame: (state) => {
            const prevFrame = state.currentFrame - state.stepSize;
            if (prevFrame >= 0) {
                state.currentFrame = prevFrame;
            } else {
                // Go to last frame if we go below 0
                state.currentFrame = Math.max(0, state.totalFrames - 1);
            }
        },
        setStepSize: (state, action: PayloadAction<number>) => {
            state.stepSize = Math.max(1, action.payload);
        },
        setTotalFrames: (state, action: PayloadAction<number>) => {
            state.totalFrames = action.payload;
            // Ensure current frame is still valid
            if (state.currentFrame >= action.payload) {
                state.currentFrame = Math.max(0, action.payload - 1);
            }
        },
    },
});

export const {
    setIsPlaying,
    setCurrentFrame,
    nextFrame,
    previousFrame,
    setStepSize,
    setTotalFrames,
} = playbackControlSlice.actions;

export default playbackControlSlice.reducer;
