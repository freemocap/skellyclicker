import React, {createContext, ReactNode, useContext} from "react";
import {useWebSocket, FrameData} from "@/hooks/websocket-context/useWebSocket";

interface WebSocketContextProps {
    isConnected: boolean;
    connect: () => void;
    disconnect: () => void;
    requestFrame: (frameNumber: number) => void;
    latestFrameData: FrameData | null;
}

interface WebSocketProviderProps {
    url: string;
    children: ReactNode;
}

const WebSocketContext = createContext<WebSocketContextProps | undefined>(undefined);

export const WebSocketContextProvider: React.FC<WebSocketProviderProps> = ({url, children}) => {
    const {isConnected, connect, disconnect, requestFrame, latestFrameData} = useWebSocket(url);

    return (
        <WebSocketContext.Provider value={{isConnected, connect, disconnect, requestFrame, latestFrameData}}>
            {children}
        </WebSocketContext.Provider>
    )
}

export const useWebSocketContext = () => {
    const context = useContext(WebSocketContext);
    if (!context) {
        throw new Error('useWebSocketContext must be used within a WebSocketProvider');
    }
    return context;
};