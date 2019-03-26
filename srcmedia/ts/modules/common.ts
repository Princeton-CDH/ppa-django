abstract class Reactive<Props> {
    element: HTMLElement

    constructor(element: HTMLElement) {
        this.element = element
    }

    abstract async update(props: Props): Promise<void>
}

export {
    Reactive,
}