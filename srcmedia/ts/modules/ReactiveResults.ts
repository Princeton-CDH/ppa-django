import { Reactive } from './common'
import { ImageLazyLoader } from '../../js/modules/LazyLoad'

type Props = string

class ReactiveResults extends Reactive<Props> {
    async update(props: Props): Promise<void> {
        this.element.innerHTML = props // update the results
        new ImageLazyLoader($('img[data-src]').get()) // rebind lazy load
        document.dispatchEvent(new Event('ZoteroItemUpdated', { // notify Zotero of changed results
            bubbles: true,
            cancelable: true
        }))
    }
}

export default ReactiveResults