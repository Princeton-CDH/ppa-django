interface Component {
    update: (data: any) => void,
}

interface Clearable {
    clear: () => void,
}

class KeywordSearch implements Component, Clearable {
    constructor() {
        
    }
    update(data: String) {
        
    }
    clear() {
        console.log('clearing')
    }
}

export default KeywordSearch