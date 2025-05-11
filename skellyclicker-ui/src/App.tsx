import React from 'react';
import {PaperbaseContent} from "@/layout/paperbase_theme/PaperbaseContent";
import {Provider} from "react-redux";
import {AppStateStore} from "@/store/AppStateStore";


function App() {
    return (
        <Provider store={AppStateStore}>
            <PaperbaseContent/>
        </Provider>
    );
}

export default App;
