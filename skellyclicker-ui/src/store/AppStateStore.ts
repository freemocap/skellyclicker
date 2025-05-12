// skellyclicker-ui/src/store/AppStateStore.ts
import {configureStore} from "@reduxjs/toolkit"
import {logRecordsSlice} from "@/store/slices/logRecordsSlice";
import {type TypedUseSelectorHook, useDispatch, useSelector} from "react-redux";
import {themeSlice} from "@/store/slices/themeSlice";
import {playbackControlSlice} from "@/store/slices/playbackControlSlice";
import {clientApi} from "@/services/clientApi";

export const AppStateStore = configureStore({
    reducer: {
        logRecords: logRecordsSlice.reducer,
        theme: themeSlice.reducer,
        playbackControl: playbackControlSlice.reducer,
        [clientApi.reducerPath]: clientApi.reducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware().concat(clientApi.middleware),
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
export const useAppDispatch = () => useDispatch<AppDispatch>()
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
